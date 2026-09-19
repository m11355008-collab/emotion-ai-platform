# questionnaires.py
#
# 這個檔案定義前測、後測要用到的所有問卷。
#
# ✅ EES、IRI、ERQ、DDI 四份量表皆已確認並填入正式題目（見各量表定義下方的
#    註解說明來源與核對過程）。四份量表目前均無佔位文字。
# 已確認的中文版出處如下：
#
#   EES：Chan, R. C. K., Wang, Y., Li, H., Shi, Y., Wang, Y., Liu, W., & Huang, J.
#        (2010). A 2-stage Factor Analysis of the Emotional Expressivity Scale
#        in the Chinese Context. Psychologia, 53(1), 44–50.
#        DOI: 10.2117/psysoc.2010.44
#        〔已完成：17 題文字已逐題比對 Chan (2010) Table 1 因素負荷量核實〕
#
#   IRI：詹志禹 (1987)．年級、性別角色、人情取向與同理心的關係
#        （碩士論文）．國立政治大學教育研究所．〔原始 22 題中文翻譯版〕
#        信效度驗證：張鳳鳳、董毅、汪凱、詹志禹、謝倫芳 (2010)．
#        中文版人際反應指針量表（IRI-C）的信度及效度研究．
#        中國臨床心理學雜誌，18(2)，155–157。
#
#   ERQ：王力、柳恒超、李中權、杜衛 (2007)．情緒調節問卷中文版的信效度研究．
#        中國健康心理學雜誌，(06)，503–505。
#        DOI: 10.13342/j.cnki.cjhp.2007.06.012
#
#   DDI：Kahn, J. H., Wei, M., Su, J. C., Han, X., & Strojewska, A. (2017).
#        Distress Disclosure and Psychological Functioning Among Taiwanese
#        Nationals and European Americans: The Moderating Roles of Mindfulness
#        and Nationality. Journal of Counseling Psychology, 64(3), 292–301.
#        （此研究直接以台灣樣本施測，適用性佳）
#        〔已完成：12 題「心理學網」繁體中文版題目已逐題對照 Kahn 官方英文題本
#        (about.illinoisstate.edu/jhkahn/distress-disclosure-index/) 核實題序與
#        反向計分題（2, 4, 5, 8, 9, 10）完全一致〕
#
# 取得上述論文全文、核對正式題目後，你必須：
#   1. 把下面 items 裡的 "text" 換成正式題目
#   2. 確認 scale_min/scale_max、reverse（反向計分題）是否與中文版一致
#      （反向計分題常常跟英文原版不同）
#   3. 依論文的引用格式要求，在論文中正確標註出處
#
# 除了這四份，以下三份是本研究自行設計的，可以直接使用、不受此限：
#   - 學習成效書寫任務（來自你的質性編碼簿，見研究方法定案文件（六））
#   - 干擾變項問卷（背景變項，見定案文件（九））
#   - 互動體驗問卷（後測專用，見定案文件（六））

from dataclasses import dataclass, field
from typing import Literal

QuestionType = Literal["likert", "open_text", "single_choice"]


@dataclass
class QuestionnaireItem:
    id: str                 # 題號，例如 "EES_01"
    text: str                # 題目文字
    qtype: QuestionType = "likert"
    scale_min: int = 1
    scale_max: int = 5
    scale_min_label: str = "非常不同意"
    scale_max_label: str = "非常同意"
    reverse: bool = False    # 是否為反向計分題
    choices: list[str] = field(default_factory=list)  # 僅 single_choice 使用


@dataclass
class Questionnaire:
    id: str                  # 問卷代號，例如 "EES"
    name: str                 # 顯示名稱
    administer_at: list[str]  # ["pre"], ["post"], 或 ["pre", "post"]
    items: list[QuestionnaireItem]


# ============================================================
# 需要正式題目的量表（佔位中，正式收案前必須替換）
# ============================================================

EES = Questionnaire(
    id="EES",
    name="情緒表達量表 (Emotional Expressivity Scale, Kring et al., 1994；中文版：Chan et al., 2010)",
    administer_at=["pre", "post"],
    items=[
        # 題目文字與反向計分（reverse）已逐題比對 Chan et al. (2010) Table 1
        # 的因素負荷量表核實，與原文 17 題、11 反向／6 正向的結構完全吻合。
        # 計分方式：依原始 Kring 版本採「單一總分」（加總全部 17 題），
        # 未依 Chan (2010) 因素分析拆分之二因子（情緒抑制／情緒表達）分開計分，
        # 此決定已於研究方法定案文件（六）中註明理由。
        QuestionnaireItem(id="EES_01", text="我認為我自己是一個愛表達情緒的人。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是"),
        QuestionnaireItem(id="EES_02", text="人們認為我不是一個情緒化的人。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_03", text="我隱藏自己的感情。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_04", text="我常被別人認為是冷漠的。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_05", text="人們可以看出我的情緒狀況。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是"),
        QuestionnaireItem(id="EES_06", text="我在別人面前表現情緒。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是"),
        QuestionnaireItem(id="EES_07", text="我不喜歡讓別人知道我的情感如何。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_08", text="我能在別人面前哭。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是"),
        QuestionnaireItem(id="EES_09", text="即使我的情緒非常激動，我也不讓別人看出我的情感。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_10", text="別人不容易看出我的情感怎樣。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_11", text="我不是一個愛表達情緒的人。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_12", text="即使我正在體驗著強烈的情感，我也不會把它們表現出來。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_13", text="我掩飾不住自己的情感。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是"),
        QuestionnaireItem(id="EES_14", text="別人認為我是一個很情緒化的人。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是"),
        QuestionnaireItem(id="EES_15", text="我不對別人表達自己的情緒。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_16", text="我的真實情感與別人所認為的不同。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
        QuestionnaireItem(id="EES_17", text="我抑制自己的情感。",
                           scale_min=1, scale_max=6, scale_min_label="從不", scale_max_label="總是", reverse=True),
    ],
)

IRI = Questionnaire(
    id="IRI",
    name="人際反應指標 (Interpersonal Reactivity Index, Davis, 1983；中文版：詹志禹, 1987)",
    administer_at=["pre", "post"],
    items=[
        # 題目文字取自詹志禹 (1987，國立政治大學教育研究所碩士論文) 附錄四原始
        # 28 題翻譯版，扣除該論文標註「修訂後已刪除」之 6 題（原始題號
        # 1、3、13、15、19、20），重新編號為 22 題。
        # 分量表歸屬已與張鳳鳳等 (2010) 論文表3之因素負荷結果逐題交叉核對，
        # 完全吻合：觀點取替(PT)=6,9,15,19,22；個人痛苦(PD)=4,8,13,18,21；
        # 幻想力(FS)=3,5,10,12,17,20；同理關懷(EC)=1,2,7,11,14,16。
        # 計分：Likert 5 點（0-4，從不恰當到非常恰當），依題目內容標註 reverse。
        QuestionnaireItem(id="IRI_01", text="對那些比我不幸的人，我經常有心軟和關懷的感覺。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_02", text="有時候當其他人有困難或問題時，我並不為他們感到很難過。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當", reverse=True),
        QuestionnaireItem(id="IRI_03", text="我的確會投入小說人物中的感情世界。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_04", text="在緊急狀況中，我感到擔憂、害怕而難以平靜。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_05", text="看電影或看戲時，我通常是旁觀的，而且不常全心投入。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當", reverse=True),
        QuestionnaireItem(id="IRI_06", text="在做決定前，我試著從爭論中去看每個人的立場。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_07", text="當我看到有人被別人利用時，我有點感到想要保護他們。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_08", text="當我處在一個情緒非常激動的情況中時，我往往會感到無依無靠，不知如何是好。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_09", text="有時候我想像從我的朋友的觀點來看事情的樣子，以便更瞭解他們。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_10", text="對我來說，全心地投入一本好書或一部好電影中，是很少有的事。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當", reverse=True),
        QuestionnaireItem(id="IRI_11", text="其他人的不幸通常不會帶給我很大的煩憂。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當", reverse=True),
        QuestionnaireItem(id="IRI_12", text="看完戲或電影之後，我會覺得自己好像是劇中的某一個角色。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_13", text="處在緊張情緒的狀況中，我會驚慌害怕。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_14", text="當我看到有人受到不公平的對待時，我有時並不感到非常同情他們。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當", reverse=True),
        QuestionnaireItem(id="IRI_15", text="我相信每個問題都有兩面觀點，所以我常試著從這不同的觀點來看問題。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_16", text="我認為自己是一個相當軟心腸的人。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_17", text="當我觀賞一部好電影時，我很容易站在某個主角的立場去感受他的心情。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_18", text="在緊急狀況中，我緊張得幾乎無法控制自己。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_19", text="當我對一個人生氣時，我通常會試著去想一下他的立場。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_20", text="當我閱讀一篇引人的故事或小說時，我想像著：如果故事中的事件發生在我身上，我會感覺怎麼樣？",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_21", text="當我看到有人發生意外而極需幫助的時候，我緊張得幾乎精神崩潰。",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
        QuestionnaireItem(id="IRI_22", text="在批評別人前，我會試著想像：假如我處在他的情況，我的感受如何？",
                           scale_min=0, scale_max=4, scale_min_label="不恰當", scale_max_label="非常恰當"),
    ],
)

ERQ = Questionnaire(
    id="ERQ",
    name="情緒調節量表 (Emotion Regulation Questionnaire, Gross & John, 2003；中文版：王力等, 2007)",
    administer_at=["pre", "post"],
    items=[
        # 題目文字取自「好晴天身心診所」繁體中文版，逐題依內容比對 Gross & John
        # (2003) 原始英文題目（Table 2）後，交叉確認分量表分組：認知重評＝
        # 1,3,5,7,8,10；表達抑制＝2,4,6,9，與王力等(2007)論文描述之題號分組
        # 完全吻合，交叉驗證信心程度高。無反向計分題（原始量表無反向題）。
        # 7 點量表：1=完全不同意 ～ 7=完全同意。
        QuestionnaireItem(id="ERQ_01", text="當我想要感受更多正面情緒（如快樂或愉悅）時，我會改變我對事情的想法。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_02", text="我把我的情緒藏在心裡。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_03", text="當我想要減少負面情緒（如悲傷或憤怒）時，我會改變我對事情的想法。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_04", text="當我感受到正面情緒時，我會小心不要表達出來。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_05", text="面對壓力情境時，我會用一種讓自己冷靜下來的方式去思考它。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_06", text="我會控制自己的情緒，不讓它們表現出來。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_07", text="當我想要感受更多正面情緒時，我會改變我看待事情的角度。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_08", text="我會用改變想法的方式來控制自己的情緒。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_09", text="當我感受到負面情緒時，我會確保不把它表達出來。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
        QuestionnaireItem(id="ERQ_10", text="當我想要減少負面情緒時，我會改變我看待事情的方式。",
                           scale_min=1, scale_max=7, scale_min_label="完全不同意", scale_max_label="完全同意"),
    ],
)

DDI = Questionnaire(
    id="DDI",
    name="情緒揭露傾向量表 (Distress Disclosure Index, Kahn & Hessling, 2001)",
    administer_at=["pre", "post"],
    items=[
        # 題目文字取自「心理學網」繁體中文版，逐題對照 Kahn 官方英文題本
        # (about.illinoisstate.edu/jhkahn/distress-disclosure-index/) 確認題序與
        # 反向計分題完全一致（反向題：2, 4, 5, 8, 9, 10）。
        # 5 點量表：1=非常不同意 ～ 5=非常同意。
        QuestionnaireItem(id="DDI_01", text="在我難過的時候，我通常向朋友傾訴。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意"),
        QuestionnaireItem(id="DDI_02", text="我不願意談論自己的問題。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意", reverse=True),
        QuestionnaireItem(id="DDI_03", text="當我身上發生不愉快的事情時，我經常找人談論這些事情。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意"),
        QuestionnaireItem(id="DDI_04", text="我一般不和人談論那些使我難過的事情。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意", reverse=True),
        QuestionnaireItem(id="DDI_05", text="當我感到沮喪或難過的時候，我總是獨自承擔。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意", reverse=True),
        QuestionnaireItem(id="DDI_06", text="我會找人談論我的問題。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意"),
        QuestionnaireItem(id="DDI_07", text="當我心情不好的時候，我會找朋友聊天。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意"),
        QuestionnaireItem(id="DDI_08", text="如果我難過，我最不願意找別人傾訴。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意", reverse=True),
        QuestionnaireItem(id="DDI_09", text="當我遇到難處的時候，我最不願意找別人談論這些困難。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意", reverse=True),
        QuestionnaireItem(id="DDI_10", text="當我痛苦的時候，我不會告訴任何人。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意", reverse=True),
        QuestionnaireItem(id="DDI_11", text="當我心情不好的時候，我通常找別人聊天。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意"),
        QuestionnaireItem(id="DDI_12", text="我願意把我不高興的事告訴別人。",
                           scale_min=1, scale_max=5, scale_min_label="非常不同意", scale_max_label="非常同意"),
    ],
)


# ============================================================
# 自行設計的問卷（可直接使用）
# ============================================================

LEARNING_OUTCOME_TASK = Questionnaire(
    id="LEARNING_OUTCOME",
    name="學習成效書寫任務",
    administer_at=["pre", "post"],
    items=[
        QuestionnaireItem(
            id="LOT_01",
            text=(
                "請描述一次讓你印象深刻的情緒經驗（發生了什麼事、你當時的感受、後來怎麼處理）。\n"
                "※ 這一題為必填，用意是確保前後測都有資料可以比較。但你不需要描述任何"
                "不想透露的具體內容——如果不想寫，請直接輸入「不願透露」四個字即可視為完成作答，"
                "不會影響你的參與資格。"
            ),
            qtype="open_text",
        ),
    ],
)

COVARIATES_SURVEY = Questionnaire(
    id="COVARIATES",
    name="干擾變項問卷（背景變項）",
    administer_at=["pre"],
    items=[
        QuestionnaireItem(id="COV_01", text="我對 AI 對話的操作方式感到熟悉。"),
        QuestionnaireItem(
            id="COV_02",
            text="我平均每週使用 AI 的頻率",
            qtype="single_choice",
            choices=["幾乎不用", "1-2 次", "3-5 次", "每天"],
        ),
        QuestionnaireItem(id="COV_03", text="我習慣用文字聊天表達想法。"),
        QuestionnaireItem(id="COV_04", text="我覺得自己的打字速度算快。"),
        QuestionnaireItem(id="COV_05", text="我對角色扮演活動感到自在且願意投入想像。"),
        QuestionnaireItem(id="COV_06", text="我認為情境模擬有助於學習與理解。"),
        QuestionnaireItem(id="COV_07", text="當我情緒低落時，我願意談論自己的感受。"),
        QuestionnaireItem(id="COV_08", text="我覺得用文字描述情緒是容易的。"),
    ],
)

DEMOGRAPHICS = Questionnaire(
    id="DEMOGRAPHICS",
    name="基本資料",
    administer_at=["pre"],
    items=[
        QuestionnaireItem(id="DEMO_01", text="年齡", qtype="open_text"),
        QuestionnaireItem(
            id="DEMO_02", text="性別", qtype="single_choice",
            choices=["女", "男", "不願透露", "其他"],
        ),
        QuestionnaireItem(id="DEMO_03", text="年級", qtype="open_text"),
    ],
)

INTERACTION_EXPERIENCE_SURVEY = Questionnaire(
    id="INTERACTION_EXPERIENCE",
    name="互動體驗問卷（僅後測）",
    administer_at=["post"],
    items=[
        QuestionnaireItem(id="IE_01", text="我覺得對方（AI／互動對象）理解我的感受。"),
        QuestionnaireItem(id="IE_02", text="這次的對話讓我覺得自然、不生硬。"),
        QuestionnaireItem(id="IE_03", text="我在表達情緒時感到舒適自在。"),
        QuestionnaireItem(id="IE_04", text="這次互動讓我對自己的情緒有新的體會或啟發。"),
    ],
)


# 前測、後測各自要跑哪些問卷，依序排列
PRETEST_QUESTIONNAIRES = [DEMOGRAPHICS, COVARIATES_SURVEY, EES, IRI, ERQ, DDI, LEARNING_OUTCOME_TASK]
POSTTEST_QUESTIONNAIRES = [EES, IRI, ERQ, DDI, LEARNING_OUTCOME_TASK, INTERACTION_EXPERIENCE_SURVEY]
