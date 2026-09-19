# survey.py
#
# 管理「一連串問卷要怎麼依序跑完」的邏輯，完全不依賴 Gradio，
# 所以可以直接用一般的 Python 測試驗證，不需要開瀏覽器。
# Gradio 介面（app.py）只負責「畫出畫面」跟「呼叫這裡的邏輯」，
# 邏輯本身的對錯在這一層就能先確認完畢。

from dataclasses import dataclass, field
from questionnaires import Questionnaire
import logger


@dataclass
class SurveySession:
    """管理一位參與者在「前測」或「後測」階段，依序作答多份問卷的過程。"""
    participant_id: str
    group: str
    session: str                       # "pre" 或 "post"
    questionnaires: list[Questionnaire]
    q_index: int = 0                    # 目前跑到第幾份問卷（0-based）
    answers: dict = field(default_factory=dict)  # {(quesionnaire_id, item_id): response}
    _current_started: bool = False

    def __post_init__(self):
        if self.session not in ("pre", "post"):
            raise ValueError(f"session 必須是 'pre' 或 'post'，收到：{self.session!r}")

    @property
    def current_questionnaire(self) -> Questionnaire | None:
        if self.q_index >= len(self.questionnaires):
            return None
        return self.questionnaires[self.q_index]

    @property
    def is_finished(self) -> bool:
        return self.q_index >= len(self.questionnaires)

    def start_current(self) -> None:
        """在畫面顯示目前這份問卷的當下呼叫一次，記錄這份問卷的開始時間。
        重複呼叫不會重複記錄（同一份問卷只記一次 start）。"""
        q = self.current_questionnaire
        if q is None or self._current_started:
            return
        phase = f"{self.session}test_{q.id}"
        logger.log_process_event(self.participant_id, self.group, phase, "start")
        self._current_started = True

    def record_answer(self, item_id: str, response: str) -> None:
        """記錄目前這份問卷裡，某一題的作答內容。"""
        q = self.current_questionnaire
        if q is None:
            raise RuntimeError("已經沒有問卷可以作答了，questionnaires 已跑完。")
        self.answers[(q.id, item_id)] = response
        logger.log_questionnaire_response(
            self.participant_id, self.group, self.session, q.id, item_id, response
        )

    def current_answers_complete(self) -> bool:
        """檢查目前這份問卷是否每一題都已作答。"""
        q = self.current_questionnaire
        if q is None:
            return True
        return all((q.id, item.id) in self.answers for item in q.items)

    def advance(self) -> None:
        """完成目前這份問卷，記錄結束時間，前進到下一份。
        若目前這份還有題目沒作答，會直接拋出例外，避免資料不完整卻被跳過。"""
        q = self.current_questionnaire
        if q is None:
            return
        if not self.current_answers_complete():
            missing = [item.id for item in q.items if (q.id, item.id) not in self.answers]
            raise RuntimeError(f"問卷 {q.id} 尚有題目未作答：{missing}")
        phase = f"{self.session}test_{q.id}"
        logger.log_process_event(self.participant_id, self.group, phase, "end")
        self.q_index += 1
        self._current_started = False
