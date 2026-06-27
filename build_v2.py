# -*- coding: utf-8 -*-
"""
游戏王MD氪金指南 · v2（对标回形针）。23 场景：旁白(含 Fish 标签) + 先音后画面分镜。
s00 是 17s 冷启动开头(先勾人再自我介绍)，其后 s01..s21 是正片。真相源
assets/氪金指南_v2数据与分镜.md。组件 v2lib.py。运行时见 templates/scene_base.html。

用法： python build_v2.py [doctor|scripts|tts|timing|build|preview|cover|chapters|render|merge|verify|cleanup|ship|reset|all]
  doctor   渲染前体检：ffmpeg/ffprobe/背景/Fish key/playwright/assets 是否就绪
  build    片段嵌底板 -> scene_html/（改了文案/分镜先跑这个）
  preview  生成 output/preview.html，浏览器里逐场景「动态」自检（渲染前必看）
  render   逐帧抓取叠背景 -> video_track.mp4，并自动接 merge 出带声音的成片
  cover    渲染 output/cover.png(16:9) 与 output/cover_4x3.png(4:3，毛玻璃原画底)
  chapters 生成 output/chapters.txt 与 章节管理.txt（B站章节）
  verify   核对成片/封面已生成且非空（就绪自检）
  cleanup  清理临时分片/中间产物，回收 NVMe
  ship     verify 通过则 cleanup，一键收尾
  reset    清空可再生工作区（raw_audio/srt/scene_html/output/durations）为下期视频腾位
  all      端到端（tts/timing 已幂等：配音/转写齐全会自动跳过，不再覆盖审过的配音）
注意：tts/timing 现已幂等——raw_audio/ 配音齐全时 `all` 会自动跳过合成与转写
（要强制重配音：`python build_v2.py tts force`）。日常迭代用 `build`→`preview`→（满意再）`render`。
"""
import os, sys, glob, json, pathlib, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, v2lib as L
from pipeline import fish_tts, durations as dur_mod, transcribe, build_scene, render, merge
from pipeline import chapters as chapters_mod, preview as preview_mod, cleanup as cleanup_mod

INK, ACCENT, RED, GOLD = L.INK, L.ACCENT, L.RED, L.GOLD
M, CX, CY, COL = L.M, L.CX, L.CY, L.COL


# ====================================================================== scenes
def s00_open():
    # cold-open: a 12s hook that earns the click before s01 introduces itself.
    # The MD key art rides the right side, feathered into the glass (premium, not
    # a sticker); text stays left of x≈2200 so it never collides with the art.
    return (
        L.hero_feather("场景0毛玻璃图.jpg", 2360, 500, 1240, 1440, cue="官方", delay=0.4, scrim=0.30)
        + L.kicker("游戏王 MASTER DUEL · 氪金指南", M, 520, delay=0.2, anim="kicker-zoom")
        + L.type_in("官方渠道，把钻买便宜一大截", M, 810, lvl=1, cue="便宜", delay=0.2)
        + L.rule(M+4, 868, 1760, delay=0.7)
        + L.text("不碰代充", M, 1150, lvl=2, cue="代充", delay=0.0, fill=ACCENT, anim="fade-up")
        + L.text("不碰黑卡", M+780, 1150, lvl=2, cue="黑卡", delay=0.0, fill=ACCENT, anim="fade-up")
        + L.text("不怕封号", M+1560, 1150, lvl=2, cue="封号", delay=0.0, fill=ACCENT, anim="fade-up")
        + L.text("听着像智商税？这套方法我自己完整跑了一趟。", M, 1430, lvl=3, cue="智商税", delay=0.0, anim="fade-up")
        + L.pop("每一分钱、每一个坑，都给你摆明白", M, 1660, lvl=2, cue="摆明白", delay=0.0, fill=GOLD)
    )

S00 = "游戏王 MD 的钻，走官方正规渠道，能买得比商店便宜一大截——不碰代充、不碰黑卡，也不怕封号。[pause]听着像智商税？这套方法，我自己完整跑了一趟。每一分钱、每一个坑，这期都给你摆明白。"


def s01_hook():
    return (
        L.kicker("游戏王 MASTER DUEL · 低成本安全氪金", M, 360, delay=0.2)
        + L.num(36, M, 720, lvl=0, cue="三十六", delay=0.3, dur=0.9, prefix="¥", fill=INK)
        + L.text("= 1000 钻石", M+560, 720, lvl=2, cue="一千钻石", delay=0.3, anim="fade-left")
        + L.rule(M+4, 770, 1100, delay=0.6)
        # 不是…三连，划掉
        + L.text("不是代充", M, 980, lvl=3, cue="代充", delay=0.2, fill=RED, anim="fade-left")
        + L.strike(M-10, 952, 360, cue="代充", delay=0.45)
        + L.text("不是黑卡", M+520, 980, lvl=3, cue="黑卡", delay=0.2, fill=RED, anim="fade-left")
        + L.strike(M+510, 952, 360, cue="黑卡", delay=0.45)
        + L.text("不是盗刷", M+1040, 980, lvl=3, cue="倒刷", delay=0.2, fill=RED, anim="fade-left")
        + L.strike(M+1030, 952, 360, cue="倒刷", delay=0.45)
        + L.stamp("100% 官方绿卡", 1080, 1320, lvl=2, cue="百分之百官方", delay=0.0, fill=ACCENT)
        # 亲测悬念
        + L.text("这一次我实测", 2280, 760, lvl=3, cue="五百二十七", delay=0.0, anim="fade-up")
        + L.num(527.70, 2280, 920, lvl=1, cue="五百二十七", delay=0.1, dur=1.0, prefix="¥", dec=2, fill=GOLD)
        + L.text("把所有活动钻全搬空", 2280, 1010, lvl=4, cue="全搬空", delay=0.0, opacity=1)
        + L.pop("整体 74.8%", 2280, 1240, lvl=1, cue="七四八", delay=0.0, fill=ACCENT)
        + L.text("电子雪貂饲养员 · 亲测", M, 1860, lvl=4, delay=2.0, opacity=1, fill=ACCENT)
    )

S01 = "[excited]大家好，我是电子雪貂饲养员。[pause]游戏王 Master Duel，三十六块钱，一千钻石。不是代充，不是黑卡，不是盗刷，是[emphasis]百分之百官方的正规充值。这套方法我自己跑通过。这一次，我花了五百二十七块七，把游戏里所有最划算的活动钻，[pause]全搬空了。整体，[emphasis]打了七四八折。怎么做到的？接下来我用数据，一步一步拆给你看。"


def s02_anchor():
    return (
        L.title("先把价钉死", M, 440, lvl=1, kick="官方原价 vs 我们", cue="钉死", delay=0.3)
        + L.bar_race([
            ("官方日区 · 1000钻", 50.48, INK, "价", "¥"),
            ("我们 · 倒余额", 37.8, ACCENT, "死", "¥"),
        ], x=M, y=760, track=2200, row_h=260, delay=0.0, maxv=85)
        + L.text("国区、美区更贵——它们按美元结算", M, 1480, lvl=3, cue="美元", delay=0.0, anim="fade-up")
        + L.num(61, M, 1620, lvl=2, cue="六十一", delay=0.1, prefix="¥", suffix=" 起", fill=RED)
        + L.image("美区价格.jpg", 2600, 1060, h=520, anim="wipe", cue="美元", delay=0.2)
        + L.image("美区价格 (2).jpg", 3080, 1110, w=540, anim="wipe", cue="美元", delay=0.35)
    )

S02 = "先把价钉死。官方商店，一千钻，标价一千二百日元，折下来是[emphasis]五十块四毛八。而我们这套方法，同样一千钻，成本只要三十七块八。[pause]至于国区、美区，更贵——因为它们都按[emphasis]美元结算，欢迎包一千钻要六十一块起，所以我直接弃用。"


def s02b_google():
    return (
        L.title("Google 券划算吗？", M, 440, lvl=1, kick="美区的各种优惠", cue="优惠", delay=0.3)
        + L.image("Google大师决斗-1美刀优惠券.jpg", M, 860, w=960, anim="wipe", cue="优惠", delay=0.5)
        + L.text("美区充值虽有 Google Play 满减优惠券", M, 1420, lvl=3, cue="满减", delay=0.0, anim="fade-up")
        + L.text("但因为美区底价太贵（折合 ¥61 起）", M, 1560, lvl=3, cue="底价", delay=0.0, anim="fade-up")
        + L.pop("即使用了券，也完全不划算 → 依然弃用", M, 1780, lvl=2, cue="不划算", delay=0.0, fill=RED)
    )

S02B = "另外，有人可能会说，美区经常有 Google Play 的优惠券，比如满四刀减一刀。其实我也仔细算过了，美区底价实在太贵，一千钻就要六十一块起。[pause]就算你用上了满减券，折算下来也完全不划算。所以，美区和 Google 券，我们直接弃用。"


def s03_table():
    rows = [
        ["欢迎包 1000", "1200日元", "¥50.48", "¥37.8", "限购3"],
        ["欢迎包 2000", "2400日元", "¥50.48", "¥37.8", "限购1"],
        ["活动·限时2500", "3800日元", "¥63.95", "¥47.8", "限3/年4轮"],
        ["常住大包4950", "10000日元", "¥85.0", "¥63.6", "无限"],
    ]
    return (
        L.title("官方价目表，全摆这儿", M, 380, lvl=1, kick="新号 / 活动 / 常驻 · 越买越贵", cue="全摆", delay=0.3)
        + L.compare_table(["档位", "日元", "官方千钻比", "我们", "限购"], rows,
                          x=M, y=720, colw=[560, 480, 620, 480, 420], row_h=210, delay=0.6, hi_col=3)
        + L.image("日语区官方价格.png", 2860, 700, w=760, anim="wipe", cue="欢迎包", delay=0.4)
        + L.image("官方常住10000日元=4950.png", 2860, 1180, h=520, anim="wipe", cue="大包", delay=0.6)
        + L.text("截图实证：日区商店原价", 2860, 1760, lvl=5, delay=1.0, opacity=1)
        + L.pop("整体打到 74.8%", M, 1860, lvl=2, cue="七四八", delay=0.0, fill=ACCENT)
    )

S03 = "把官方能买的，全摆一张表上。新号的两个欢迎包最划算，每千钻五十块出头；活动的限时两千五，千钻比涨到六十四；常住的大包，直接八十五——[emphasis]越买越贵。而我们这一列，每一档都是官方价乘以七成半。整体，[emphasis]打到七四八折。"


def s04_xianyu():
    return (
        L.title("那，某鱼代充呢？", M, 440, lvl=1, kick="便宜的代价", cue="代冲", delay=0.3)
        + L.num(280, M, 760, lvl=1, cue="苹果", delay=0.1, prefix="¥", suffix=" 苹果端", fill=RED)
        + L.strike(M-10, 715, 560, cue="退款", delay=2.0)
        + L.num(370, M, 940, lvl=1, cue="其他", delay=0.1, prefix="¥", suffix=" 其他端", fill=RED)
        + L.strike(M-10, 895, 560, cue="退款", delay=2.1)
        + L.chip("① 钻到账后，商家向平台退款，钱回自己手里", M, 1200, lvl=3, cue="退款", delay=2.0, color=RED)
        + L.chip("② 干脆用境外盗卡付的款", M, 1340, lvl=3, cue="境外", delay=2.3, color=RED)
        + L.text("订单站不住脚 → 轻则倒扣，重则封号", M, 1560, lvl=2, cue="封号", delay=0.0, fill=RED)
        + L.text("有风险，不是 100% 翻车——但你在拿账号赌", M, 1700, lvl=4, cue="赌", delay=0.0, opacity=1)
        + L.stamp("我们：又便宜，又安全", 2760, 1000, lvl=3, cue="安全", delay=0.0, fill=ACCENT)
    )

S04 = "那，某鱼代充呢？四千九百五十钻，苹果端两百八，其他端三百七，看着真便宜。[pause]但它凭什么便宜？要么是钻到账后，商家向平台申请退款，把钱倒回自己手里；要么，干脆用境外盗卡。[pause]这种单子站不住脚，轻则倒扣成负钻，重则封号。它有风险，倒不是百分百翻车——可你那是拿账号在赌。而我们，又便宜，又安全。"


def s05_principle():
    return (
        L.title("为什么要买 CS2 箱子？", M, 380, lvl=1, kick="走线充值的原理", cue="箱子", delay=0.3)
        + L.flow_token([
            ("人民币", "人民币", False),
            ("BUFF 低价买箱", "买箱", True),
            ("发日区小号", "小号", False),
            ("Steam 日区卖出", "卖掉", True),
            ("日元余额", "日元", True),
        ], x=440, y=1080, gap=720, delay=0.6, token_label="¥")
        + L.text("Steam 不让人民币跨区充——但饰品全区通用", M, 1560, lvl=3, cue="全区通用", delay=0.0, anim="fade-up")
        + L.pop("唯一官方允许 · 绝对安全的走线充值", M, 1720, lvl=3, cue="走线", delay=0.0, fill=ACCENT)
    )

S05 = "进实操前，先解一个最大的疑惑：我充游戏王，为什么要绕去买 CS2 的箱子？[pause]原因只有一条——Steam 不让你把人民币跨区充进日区钱包，但 Steam 的饰品，是[emphasis]全区通用的。所以我们在网易 BUFF 用人民币低价买箱，发给日区小号，再挂到 Steam 日区市场卖掉，换回日元余额。这，就是唯一官方允许、绝对安全的走线充值。"


def s06_fourstep():
    return (
        L.title("整套流程，就四步", M, 420, lvl=1, kick="先看地图，再逐个拆", cue="四步", delay=0.3)
        + L.checklist("", [
            ("第一步　备一个干净的初始小号", "小号"),
            ("第二步　绑手机令牌、养号", "令牌"),
            ("第三步　网易 BUFF 低价倒余额", "倒余额"),
            ("第四步　买光最划算的促销，离场", "离场"),
        ], x=M, y=760, delay=0.4, lvl=2)
        + L.text("只折腾这一次，这个号一辈子享受这个价", M, 1620, lvl=3, cue="一辈子", delay=0.0, fill=ACCENT, anim="fade-up")
    )

S06 = "整套流程，拆开就四步。第一步，备一个干净的初始小号。第二步，绑手机令牌、养号。第三步，去网易 BUFF 低价倒余额。第四步，买光游戏里最划算的促销，[emphasis]离场。听着不少，但你只折腾这一次，这个号，[emphasis]一辈子都享受这个价。下面，一步一步来。"


def s07_account():
    return (
        L.title("账号与区服", M, 360, lvl=1, kick="这块最多人踩坑", cue="区服", delay=0.3)
        + L.chip("纯白号挂梯子就能改区，买现成日区空白号最省事", M, 660, lvl=3, cue="空白号", delay=0.0)
        + L.chip("Steam 区定充值价，MD 区只定卡图——选日本=日区卡图", M, 820, lvl=3, cue="卡图", delay=0.0)
        + L.chip("Steam 和科乐美 ID 终身死绑，号必须干净", M, 980, lvl=3, cue="终身", delay=1.5, color=RED)
        + L.push_image("1249日元某宝截图.jpg", 2080, 600, w=1500, cue="充值卡", delay=0.3, dur=8, zoom=1.05, dx=-40, dy=-24)
        + L.callout(["实付 ¥51.98", "到账 1246 日元 → 首充1000钻 → 切日区"], M, 1340, cue="充值卡", delay=3.0, lvl=2, fill=GOLD)
    )

S07 = "先讲账号和区服，这块最多人踩坑。第一，别买所谓日区充值号，那玩意儿根本不存在。零消费的纯白号，挂个梯子就能随便改区，想省事，直接买个干净的[emphasis]日区空白号。第二，记住：真正决定充值价格的是你 Steam 的区；游戏里选哪个区只决定卡图——选日本，就用[emphasis]日区卡图，没有和谐。然后某宝买张日区充值卡，实付五十一块九毛八，到账一千二百四十六日元，首充一千钻，账号就切到了日元区。最后一句：Steam 和科乐美的 ID 终身死绑，所以号一定要干净。"


def s08_lock():
    return (
        L.title("到手立刻做三件事", M, 440, lvl=1, kick="防找回 · 上锁", cue="三件事", delay=0.3)
        + L.checklist("", [
            ("改密码", "改密码"),
            ("改绑邮箱", "邮箱"),
            ("手机装 Steam App，开手机令牌", "令牌"),
        ], x=M, y=780, delay=0.4, lvl=2)
        + L.pop("R 码（恢复码）务必截图存好", 2240, 980, lvl=2, cue="恢复码", delay=0.0, fill=RED)
        + L.text("手机一丢，没有 R 码，号就再也找不回来", 2240, 1120, lvl=4, cue="找不回", delay=0.0, opacity=1)
    )

S08 = "号一到手，立刻做三件事防找回：改密码、改绑邮箱、手机装上 Steam App 开手机令牌，把商家能找回的口子全堵死。[pause]还有个保命的东西——开令牌时系统给的 R 码，也就是恢复码，[emphasis]务必截图存好。手机要是丢了，没有它，这号就再也找不回来了。"


def s09_timing():
    return (
        L.title("最聪明的一步：算时间差", M, 360, lvl=1, kick="令牌 15 天 ⊖ 消费 7 天", cue="时间差", delay=0.3)
        + L.text("15 − 7 =", M, 720, lvl=1, cue="十五减七", delay=0.1, anim="fade-left")
        + L.pop("8 天宽限期", M+680, 720, lvl=1, cue="等于八", delay=0.0, fill=ACCENT)
        + L.timeline_scrub([
            (0.0, "Day1", "绑令牌·开始15天", "第一天", True),
            (0.32, "Day7", "充值卡首充·满7天消费", "第七天", True),
            (0.66, "Day15", "双线归零·市场解锁", "解锁", True),
            (1.0, "Day22", "箱子7天锁满·出售到账", "到账", True),
        ], x=M, y=1180, w=3200, delay=1.0)
        + L.text("新号余额真正可用 = 15 + 7 = 22 天", M, 1560, lvl=3, cue="二十二", delay=0.0, fill=ACCENT)
    )

S09 = "这是这期最聪明的一步——算时间差。令牌一开，市场冻结十五天；同时，账号得有一笔满七天的消费才准用市场。两个数一减，[emphasis]十五减七等于八，这就是宽限期：第一天绑令牌，最迟第七天充那一千钻，到第十五天双线归零、市场解锁。再买箱子，过七天交易锁，第二十二天出售到账。所以新号余额真正可用，是十五加七，[emphasis]二十二天。"


def s10_planb():
    return (
        L.title("着急党 · Plan B", M, 440, lvl=1, kick="令牌不卡你开玩", cue="不想等", delay=0.3)
        + L.text("令牌那 15 天，只卡「去 BUFF 倒余额」这一步", M, 760, lvl=2, cue="倒余额", delay=0.1, anim="fade-up")
        + L.chip("不卡你登录游戏", M, 980, lvl=3, cue="登录", delay=0.0)
        + L.chip("不卡你用初始号的免费钻抽卡", M, 1120, lvl=3, cue="钻", delay=0.0)
        + L.pop("想爽先玩，想省到极致走八天线——两不耽误", M, 1400, lvl=3, cue="两不耽误", delay=0.0, fill=ACCENT)
    )

S10 = "当然，你要是一秒都不想等：第一天改完密、绑完令牌，直接登录开玩就行。令牌那十五天，卡的只是你[emphasis]去 BUFF 倒余额这一步，它不卡你登录，也不卡你用初始号的免费钻抽卡。想立刻爽的先玩，想省到极致的走那条八天线，[emphasis]两不耽误。"


def s11_buffcfg():
    return (
        L.title("网易 BUFF 基础配置", M, 360, lvl=1, kick="手机端一键设置就行", cue="正", delay=0.3)
        + L.image("网易buff一键设置steam账号管理界面.jpg", 300, 480, h=1560, anim="wipe", cue="一键设置", delay=0.3)
        + L.hl_box(338, 1352, 668, 150, cue="自动收货", delay=0.0, color=ACCENT)
        + L.chip("用「一键绑定 Steam」绑日区小号", 1320, 700, lvl=3, cue="一键绑定", delay=0.0)
        + L.chip("Steam 库存设公开", 1320, 860, lvl=3, cue="公开", delay=0.0)
        + L.chip("打开「自动收货」，卖家报价自动接", 1320, 1020, lvl=3, cue="自动收货", delay=0.0)
        + L.image("小号的“交易 URL.png", 1320, 1180, h=820, anim="wipe", cue="交易链接", delay=0.2)
        + L.text("复制 Trade URL 粘进 BUFF —— 配置完成", 1320, 2080, lvl=3, cue="完成", delay=0.0, fill=ACCENT)
    )

S11 = "市场解锁之后，进正题，倒余额。先花一分钟把网易 BUFF 配好，手机端一键设置就行：用它的[emphasis]一键绑定 Steam，把日区小号绑进去；把 Steam 库存设成公开；再打开[emphasis]自动收货，这样卖家发来的报价，BUFF 会自动接，你不用守着手机。最后复制交易链接粘进 BUFF，配置就[emphasis]完成了。"


def s12_pick():
    return (
        L.title("选货：热潮武器箱", M, 340, lvl=1, kick="买入 vs 卖出，差价就是利润", cue="热潮", delay=0.3)
        + L.image("网易buff热潮武器箱200库存4.07.jpg", 300, 600, h=860, anim="wipe", cue="买入", delay=0.6)
        + L.callout(["买入 ¥4.06", "网易 BUFF 批量购买"], 760, 820, cue="买入", delay=0.6, lvl=1, fill=GOLD)
        + L.callout(["卖出 ¥6.18", "≈147 日元 · 扣税到手129（87%）"], 760, 1160, cue="一百四十", delay=0.0, lvl=1, fill=ACCENT)
        # 听到“看不懂”时，将上一组图片和红框无痕隐藏
        + f'<g data-anim="fade-out" {L._t("看不懂", 0.0, 0.3)}>'
        + L.image("热潮武器箱出售6.18.png", 2040, 660, w=1600, anim="wipe", cue="一百四十", delay=0.3)
        + L.hl_box(2070, 1180, 1540, 210, cue="水平线", delay=0.0, color=ACCENT)
        + f'</g>'
        + L.text("中位线整月几乎水平 = 价格稳，不怕砸盘", 760, 1500, lvl=3, cue="水平线", delay=3.0, opacity=1)
        + L.image("五大适合出售的箱子.jpg", 2040, 660, w=1600, anim="wipe", cue="看不懂", delay=0.2)
        + L.text("以后未必是热潮：汇率/箱价会变，看不懂就把截图发 AI 算", 760, 1620, lvl=4, cue="看不懂", delay=2.0, opacity=1, fill=ACCENT)
    )

S12 = "买什么？批量买 CS2 的[emphasis]热潮武器箱。网易 BUFF 上买入，一个四块零六；挂到 Steam 市场，卖六块一毛八，也就是[emphasis]一百四十多日元，扣完税到手大概一百二十九，差价就是利润。为什么选它？你看这条售价中位线，整整一个月几乎是条[emphasis]水平线，价格稳，不怕你买进去就砸盘。当然，以后未必还是热潮——汇率和箱价都会变，长期折扣可能越来越低，看不懂，就把买入价和卖出价截图，[emphasis]发给 AI 算。"


def s13_routeA():
    return (
        L.title("路线 A · 直购法", M, 420, lvl=1, kick="大多数人走这条", cue="直购", delay=0.3)
        + L.flow_token([
            ("网易 BUFF 买箱", "买箱", True),
            ("发日区小号", "小号", False),
            ("挂 Steam 市场卖", "卖掉", True),
            ("换回日元", "日元", True),
        ], x=560, y=1080, gap=820, delay=0.6, token_label="箱")
        + L.text("最简单：买、发、卖，三步到位", M, 1560, lvl=3, cue="最简单", delay=0.0, fill=ACCENT, anim="fade-up")
        + L.text("整个网易 BUFF 批量买箱，约 30 分钟就能搞定 500 块的货", M, 1700, lvl=4, cue="三十分钟", delay=0.0, opacity=1)
    )

S13 = "倒余额有两条路。先说路线 A，直购法，大多数人走这条：直接在网易 BUFF 买箱，发给日区小号，小号收到，挂上 Steam 市场卖掉，换回日元。[emphasis]最简单，买、发、卖，三步到位。补一句，整个网易 BUFF 批量买箱，大概[emphasis]三十分钟，就能搞定五百块的货。"


def s14_routeB():
    # 无痕窗口 shrunk + captions dropped below it (text used to sit on the image's
    # lower edge); right-side shots shortened so the ¥495 callout lands inside the
    # glass (was y=2020, past the 2009 bottom edge).
    return (
        L.title("路线 B · 大号转余额", M, 360, lvl=1, kick="进阶：手上有闲置余额才用", cue="进阶", delay=0.3)
        + L.image("无痕窗口.png", 300, 620, w=1000, anim="wipe", cue="无痕", delay=0.3)
        + L.hl_box(300, 668, 1000, 158, cue="无痕", delay=0.6, color=ACCENT)
        + L.text("大号用平时浏览器登录", 300, 1150, lvl=3, cue="浏览器", delay=0.0)
        + L.text("小号 Trade URL 单独开无痕窗口取", 300, 1290, lvl=3, cue="无痕", delay=0.0, fill=ACCENT)
        + L.image("购买成功.jpg", 1520, 560, h=1280, anim="wipe", cue="实测", delay=0.3)
        + L.image("消费价格.jpg", 2620, 560, h=1280, anim="wipe", cue="一百二十二", delay=0.3)
        + L.callout(["亲测 ¥495.32 · 买进 122 个热潮箱", "只掏这么点：大号还剩 ¥39 余额顶上"], 1520, 1900, cue="实测", delay=0.0, lvl=3, fill=GOLD)
    )

S14 = "路线 B，是给手上[emphasis]本来就有闲置余额的大号准备的，进阶玩法，大部分人用不上。操作有个细节：大号用你平时的浏览器登录；小号的交易链接，单独开个[emphasis]无痕窗口去取，别在一个窗口里来回切。这次我实测，网易 BUFF 上花四百九十五块三毛二，买进[emphasis]一百二十二个热潮箱——我只掏这么点，是因为大号还剩三十九块余额顶着。"


def s14b_gift():
    # 3 columns sized to the glass (x∈[240,3600]); the 3rd shot is landscape, so it
    # is sized by WIDTH (was h=1100 -> w=1555, right edge 4255 = off the glass).
    return (
        L.title("怎么把箱子给小号", M, 380, lvl=1, kick="提前 7 天买 · 好友无偿赠送", cue="箱子", delay=0.3)
        + L.image("和小号交易请求.png", 300, 600, h=1180, anim="wipe", cue="赠送", delay=0.3)
        + L.image("steam手机确认和小号交易.jpg", 1440, 560, h=1300, anim="wipe", cue="确认", delay=0.3)
        + L.image("小号同意交易礼物.png", 2180, 700, w=1360, anim="wipe", cue="保护", delay=0.3)
        + L.text("① 发起赠送", 300, 1940, lvl=3, cue="赠送", delay=0.0, fill=ACCENT)
        + L.text("② 手机确认放弃物品", 1440, 1940, lvl=3, cue="确认", delay=0.0, fill=ACCENT)
        + L.pop("③ 小号收到 · 7天保护后卖出", 2180, 1940, lvl=3, cue="保护", delay=0.0, fill=ACCENT)
    )

S14B = "拿到箱子，怎么给小号？大号提前七天买好，过了那七天交易锁，再通过好友[emphasis]无偿赠送给小号。在手机上确认这笔赠送——你需要放弃这些物品；小号收到后，会有[emphasis]七天交易保护；等保护一过，挂市场卖出。安全、合规、不伤号。"


def s15_phish():
    return (
        L.title("最后一道保险：防钓鱼", M, 440, lvl=1, kick="资金安全最重要的一关", cue="钓鱼", delay=0.3)
        + L.checklist("", [
            ("只走网易 BUFF App 里的指引", "指引"),
            ("外部网页、API 链接，一律不点", "不点"),
            ("外站要你填 Steam 账密，一律不填", "不填"),
            ("手机确认时，核对对方注册时间、等级", "核对"),
        ], x=M, y=720, delay=0.4, lvl=3)
        # 精准对齐 "句" 字时间点，文案标点同步修正
        + L.pop("不脱离网易 BUFF，不点外链，骗子就无从下手", M, 1620, lvl=2, cue="句", delay=0.0, fill=ACCENT)
    )

S15 = "最后一道保险，也是资金安全最重要的一关，防 API 钓鱼。在 Steam 收发报价，[emphasis]只走网易 BUFF App 里的指引。任何卖家买家私发的外部网页、API 链接，一律不点；任何外站让你填 Steam 账号密码，一律不填。手机确认报价时，再核对一遍对方的注册时间和等级，跟网易 BUFF 对得上才点。一句话：不脱离网易 BUFF，不点外链，骗子就[emphasis]无从下手。"


def s16_loop():
    return (
        L.title("闭环：卖出 → 充值", M, 380, lvl=1, kick="把日元变成钻石", cue="闭环", delay=0.3)
        + L.flow_token([
            ("上架等7天", "付款", False),
            ("买家付款", "付款", True),
            ("Steam扣税·到手87%", "一道", False),
            ("日元进钱包", "钱包", True),
            ("充进MD买活动钻", "活动钻", True),
        ], x=440, y=1080, gap=720, delay=0.6, token_label="¥")
        + L.text("Steam 手续费：卖家实得约 86.95%", M, 1560, lvl=3, cue="八成", delay=4.0, anim="fade-up")
        + L.pop("余额到账，买光所有活动钻——闭环完成", M, 1720, lvl=2, cue="完成", delay=0.0, fill=ACCENT)
    )

S16 = "箱子卖出，怎么变成钻？把闭环走完：上架，等过七天交易锁，买家付款，Steam 扣一道税，卖家实得大概[emphasis]八成七，日元就进了你钱包。最后，余额充进游戏，买光所有最划算的活动钻。到这儿，[emphasis]闭环就完成了。"


def s17_report():
    rows = [
        ["147 日元（当前市价）", "129 日元", "16,770", "富余 570 · 超额"],
        ["144 日元（轻微砸盘）", "126 日元", "16,380", "富余 180 · 稳稳"],
        ["143 日元（悲观阴跌）", "125 日元", "16,250", "富余 50 · 极限"],
    ]
    return (
        L.kicker("亲测成绩单 · 2026/06/27", M, 320, delay=0.2)
        + L.text("成本", CX-480, 560, lvl=3, cue="成本", delay=0.1)
        + L.num(527.70, CX-220, 560, lvl=1, cue="成本", delay=0.15, dur=1.0, prefix="¥", dec=2, fill=GOLD)
        + L.text("= 130 个热潮箱", CX+480, 560, lvl=3, cue="一百三十", delay=0.0, anim="fade-left")
        + L.compare_table(["7天后市价", "扣税到手", "130箱总到手(日元)", "对比目标 16,200"], rows,
                          x=M, y=820, colw=[820, 560, 900, 920], row_h=200, delay=0.7, hi_col=2)
        + L.text("147 平仓 → 官方原价 ¥705.51", M, 1680, lvl=3, cue="原价", delay=0.0)
        + L.pop("527.70 ÷ 705.51 = 74.8%", M, 1840, lvl=1, cue="七四八", delay=0.0, fill=ACCENT)
        # 精准切中 16.68s 的 "16" 字样图层，平滑展开动画动画说明
        + L.callout(["为什么是 16,200 钻？", "因为 4 个免费限购 + 3 个活动促销"], 2200, 1650, cue="16", delay=0.0, lvl=3, fill=GOLD)
    )

S17 = "好，上[excited]亲测成绩单。成本，五百二十七块七，买了一百三十个热潮箱。七天后按当前市价一百四十七日元直出，扣税单个到手一百二十九，一百三十个，到手[emphasis]一万六千七百七十日元，比目标一万六千二还富余五百七。就算砸盘到一百四十四，也稳稳够。算笔账：一万六千七百七十日元，官方原价要七百零五块五；我的成本五百二十七块七，除一下，[emphasis]七四八折。"


def s18_timeline22():
    return (
        L.title("一图通关 · 22 天", M, 380, lvl=1, kick="把全流程压成一条线", cue="整套流程", delay=0.3)
        + L.timeline_scrub([
            (0.0, "Day1", "改绑·开令牌·白嫖试玩", "第一天", True),
            (0.30, "Day7", "充值卡首充·切日区", "首充", True),
            (0.62, "Day15", "市场解锁·BUFF倒余额", "解锁", True),
            (1.0, "Day22", "出售到账·买光活动钻", "到账", True),
        ], x=M, y=1080, w=3200, delay=0.8)
        + L.stamp("100% 官方绿卡 · 安全解锁", CX, 1560, lvl=2, cue="绿卡", delay=0.0, fill=ACCENT)
    )

S18 = "把整套流程压成一条线：第一天，改绑、开令牌，顺手白嫖初始号的免费钻试玩。第七天，充值卡首充，切到日元区。第十五天，市场解锁，绑网易 BUFF 倒余额。再等七天，第二十二天，出售到账，买光活动钻。全程，[emphasis]官方绿卡，安全解锁。"


def s19_balance():
    return (
        L.title("它的缺点，其实没那么死", M, 360, lvl=1, kick="等多久，看你是什么号", cue="缺点", delay=0.3)
        + L.balance("缺点", [("要等", "缺点")],
                    "三档等待", [("新号 15+7 = 22 天", "新号"), ("老号 只要 7 天", "老号"), ("绑了令牌没充 14 天", "十四")],
                    tilt_to=7, x=CX, y=1150, beam=2200, delay=0.6,
                    left_color=RED, right_color=ACCENT)
        + L.text("用一次等待，换一辈子的便宜 + 100% 安全", M, 1820, lvl=3, cue="一辈子", delay=0.0, fill=ACCENT)
    )

S19 = "再说说缺点——其实没大家想的那么死板。要等，没错，但等多久看你是什么号：[emphasis]新号，十五加七，二十二天；老号，令牌早绑过，只要七天；要是绑了令牌却一直没充值，十四天。就这么点等待，换的是一辈子的便宜，加百分之百的安全。这笔账，[emphasis]我觉得值。"


def s20_gems():
    return (
        L.title("最后提醒：钻会过期", M, 360, lvl=1, kick="有偿半年作废 · 无偿不过期", cue="过期", delay=0.3)
        + L.text("有偿钻（自己买的）", 900, 740, lvl=2, cue="有偿", delay=0.1, anchor="middle", fill=GOLD)
        + L.text("保存半年会过期 → 优先花掉", 900, 880, lvl=3, cue="优先", delay=0.0, anchor="middle")
        + L.text("上限 499,999", 900, 1000, lvl=4, delay=0.6, anchor="middle", opacity=1)
        + L.text("无偿钻（活动送的）", 2940, 740, lvl=2, cue="无偿", delay=0.1, anchor="middle", fill=ACCENT)
        + L.text("永不过期 · 系统默认先扣它", 2940, 880, lvl=3, cue="不过期", delay=0.0, anchor="middle")
        + L.text("上限 9,999", 2940, 1000, lvl=4, delay=0.6, anchor="middle", opacity=1)
        + L.pop("有偿钻别囤，先花；无偿钻不急", CX, 1400, lvl=2, cue="别囤", delay=0.0, fill=ACCENT)
    )

S20 = "最后提醒一个容易让钻[emphasis]白白蒸发的细节。钻分两种：自己买的叫有偿，活动送的叫无偿。有偿钻只保存半年，半年不花就[emphasis]过期作废；无偿钻永不过期，而且系统扣费默认先扣它。所以记住：有偿钻别囤，[emphasis]优先花掉；无偿钻不急。"


def s21_cta():
    return (
        f'<g data-anim="fade-out" {L._t("下期", 0.0, 0.4)}>'
        + L.text("活动限时 2500 钻 · 3800 日元", CX, 560, lvl=2, cue="活动", delay=0.3, anchor="middle", fill=GOLD)
        + L.pop("只剩 39 天", CX, 720, lvl=1, cue="三十九", delay=0.0, fill=RED, anchor="middle")
        + L.text("这套操作 22 天够用——有充值计划，来得及", CX, 880, lvl=3, cue="来得及", delay=0.0, anchor="middle", fill=ACCENT)
        + f'</g>'
        + L.end_card("我们下期见", "一键三连 + 关注 · 钻石分平台不互通", cue="下期", delay=1.6)
    )

# 找到 S21 这一行，替换为：
S21 = "对了，那个活动的限时两千五百钻、三千八百日元，[emphasis]只剩三十九天了。而这套操作，二十二天就够——你要是有充值计划，[emphasis]完全来得及。每千钻折到三十六七块，整体七四八折，真的很划算。觉得有用，麻烦点赞、投币、收藏，一键三连，再点个关注。补一句：钻石分平台不互通，认准你充值的那个平台。我是电子雪貂饲养员，我们，下期见。[pause][pause][pause][pause][pause]"


SCENES = [
    ("s00", s00_open, S00),
    ("s01", s01_hook, S01), ("s02", s02_anchor, S02), ("s02b", s02b_google, S02B), ("s03", s03_table, S03),
    ("s04", s04_xianyu, S04), ("s05", s05_principle, S05), ("s06", s06_fourstep, S06),
    ("s07", s07_account, S07), ("s08", s08_lock, S08), ("s09", s09_timing, S09),
    ("s10", s10_planb, S10), ("s11", s11_buffcfg, S11), ("s12", s12_pick, S12),
    ("s13", s13_routeA, S13), ("s14", s14_routeB, S14), ("s14b", s14b_gift, S14B), ("s15", s15_phish, S15),
    ("s16", s16_loop, S16), ("s17", s17_report, S17), ("s18", s18_timeline22, S18),
    ("s19", s19_balance, S19), ("s20", s20_gems, S20), ("s21", s21_cta, S21),
]


# ---- chapters (B站): (0-based start scene index, 章节标题) -------------------
# Viewer-facing TOC: one clear idea per chapter, short enough to scan on a phone.
# (No "A & B" double-topics — those read as cramped/啰嗦 in the chapter bar.)
CHAPTER_GROUPS = [
    (0,  "36元买千钻？"),         # s00 + s01
    (2,  "官方价vs走线价"),     # s02 + s02b + s03
    (5,  "代充封号黑幕"),       # s04
    (6,  "走线原理解析"),      # s05
    (7,  "日区账号防找回"),       # s06 + s07 + s08
    (10, "算清22天时间差"),      # s09 + s10
    (12, "选箱子与配BUFF"),        # s11 + s12
    (14, "倒余额双路线"),        # s13 + s14 + s14b
    (17, "防API钓鱼避坑"),        # s15 + s16
    (19, "实测成本成绩单"),        # s17 + s18
    (21, "有偿钻过期机制"),          # s19 + s20 + s21
]

# ---- covers (bespoke HTML -> PNG; templates are project-specific) ------------
COVERS = [  # (template, output_png, {placeholder: file_path_to_uri}, viewport, scale)
    ("cover_md.html",    "cover.png",     {}, (3840, 2160), 1),
    ("cover_md_43.html", "cover_4x3.png",
     {"@@ART@@": os.path.join(config.DIR_ASSETS, "场景0毛玻璃图.jpg")}, (1600, 1200), 2),
]


def render_covers():
    """Screenshot each bespoke cover template to output/. Vector + one image, so
    the result is razor sharp (no video frame-grab softness)."""
    import asyncio
    from playwright.async_api import async_playwright
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def run():
        async with async_playwright() as p:
            try: b = await p.chromium.launch(headless=True, channel="chrome")
            except Exception: b = await p.chromium.launch(headless=True)
            for tpl, outname, repl, (vw, vh), scale in COVERS:
                html = pathlib.Path(os.path.join(config.ROOT, "templates", tpl)).read_text(encoding="utf-8")
                for ph, path in repl.items():
                    html = html.replace(ph, pathlib.Path(path).as_uri())
                tmp = os.path.join(config.DIR_SCENE, f"_cover_{outname}.html")
                pathlib.Path(tmp).write_text(html, encoding="utf-8")
                ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=scale)
                pg = await ctx.new_page(); await pg.goto(pathlib.Path(tmp).as_uri())
                out = os.path.join(config.DIR_OUTPUT, outname)
                await pg.screenshot(path=out, type="png"); await ctx.close()
                os.remove(tmp); print(f"[cover] -> {out}  ({vw}x{vh}@{scale}x)")
            await b.close()
    config.ensure_dirs()
    asyncio.run(run())


def write_chapters():
    """Bilibili chapter markers: output/chapters.txt (paste-ready) + a richer
    章节管理.txt (markers + per-scene reference for manual tweaking)."""
    durs = _durs()
    chs = chapters_mod.from_scene_groups(durs, CHAPTER_GROUPS)
    chapters_mod.write(chs)  # -> output/chapters.txt
    # richer management file at the repo root
    offs, acc = [], 0.0
    for d in durs:
        offs.append(acc); acc += d
    lines = ["游戏王MD氪金指南 · 章节管理",
             f"全片 {chapters_mod.fmt_ts(acc)} · {len(SCENES)} 场景 · {len(CHAPTER_GROUPS)} 章节",
             "用法：复制下面【章节标记】整块，粘进 B 站投稿页「章节文本编辑器」一键生成。",
             "格式 MM:SS 标题；首行须 00:00；相邻章节间隔 ≥5 秒。", "",
             "──────── 章节标记（复制这块）────────"]
    lines += [f"{chapters_mod.fmt_ts(t)} {title}" for t, title in chs]
    lines += ["", "──────── 场景对照（自己定位用，不用粘）────────"]
    for i, (name, _, _) in enumerate(SCENES):
        lines.append(f"#{i+1:02d}  {chapters_mod.fmt_ts(offs[i])}  {name:5s}  {durs[i]:5.1f}s")
    out = os.path.join(config.ROOT, "章节管理.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[chapters] -> {out}")


# ====================================================================== driver
def write_scripts():
    config.ensure_dirs()
    for i, (_, _, text) in enumerate(SCENES, 1):
        with open(os.path.join(config.DIR_SCRIPTS, f"script_{i:02d}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"[v2] wrote {len(SCENES)} scripts")


def build_all():
    config.ensure_dirs()
    paths = []
    for i, (name, fn, _) in enumerate(SCENES, 1):
        srt = os.path.join(config.DIR_SRT, f"srt_{i:02d}.json")
        out = os.path.join(config.DIR_SCENE, f"scene_{i:02d}.html")
        paths.append(build_scene.build(fn(), out, srt=srt if os.path.exists(srt) else None))
    return paths


def _durs():
    with open(config.DURATIONS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _count(dir_, pat):
    return len(glob.glob(os.path.join(dir_, pat)))


def doctor():
    """Preflight: confirm the toolchain + inputs are ready BEFORE a long render,
    so a missing ffmpeg / background / key fails in 1s instead of 80min in."""
    import shutil as _sh
    rows = []
    def chk(name, cond, hint=""):
        rows.append(cond); print(f"  [{'OK' if cond else 'XX'}] {name}" + ("" if cond else f"   -> {hint}"))
    chk("ffmpeg",        _sh.which("ffmpeg") is not None,  "install ffmpeg and add to PATH")
    chk("ffprobe",       _sh.which("ffprobe") is not None, "ships with ffmpeg")
    chk("background mp4", os.path.exists(config.BG_VIDEO), "background/background_4k.mp4 missing")
    chk("FISH_API_KEY",  bool(config.FISH_API_KEY),        "set secret_local.py / env (only needed for tts)")
    chk("BGM (optional)", os.path.exists(config.BGM_PATH), "drop bgm.mp3 for ducked music (optional)")
    try:
        import playwright  # noqa: F401
        chk("playwright", True)
    except Exception:
        chk("playwright", False, "pip install playwright && playwright install chrome")
    n_assets = _count(config.DIR_ASSETS, "*") if os.path.exists(config.DIR_ASSETS) else 0
    chk("assets/", n_assets > 0, "drop your screenshots / art in assets/")
    ok = all(rows)
    print("[doctor] READY" if ok else "[doctor] NOT READY - fix the XX rows above")
    return ok


def reset_workspace(confirm):
    """Wipe the regenerable per-project workspace so THIS FOLDER can host the next
    video. Keeps assets/ (you swap art by hand) and the committed scaffold/code."""
    targets = [config.DIR_AUDIO, config.DIR_SRT, config.DIR_SCENE, config.DIR_RENDERED, config.DIR_OUTPUT]
    if confirm != "yes":
        print("[reset] DRY-RUN. Would DELETE: raw_audio/ srt_data/ scene_html/ rendered/ "
              "output/ + durations.json")
        print("[reset] (kept: assets/ scripts/ and all committed code).  Confirm with:")
        print("[reset]   python build_v2.py reset yes")
        return
    import shutil as _sh
    for d in targets:
        _sh.rmtree(d, ignore_errors=True)
    try: os.remove(config.DURATIONS_JSON)
    except OSError: pass
    config.ensure_dirs()
    print("[reset] workspace cleared. Next: swap assets/, edit SCENES in build_v2.py, "
          "then `python build_v2.py doctor` → `all`.")


def main():
    argv = sys.argv[1:]
    stage = argv[0] if argv else "all"
    rest = argv[1:]
    force = "force" in rest

    if stage == "doctor":
        sys.exit(0 if doctor() else 1)
    if stage == "reset":
        return reset_workspace(rest[0] if rest else "")

    if stage in ("scripts", "all"):
        write_scripts()
    if stage in ("tts", "all"):
        # Idempotent: approved narration is precious. Skip if every clip exists
        # (this is the fix for the old "don't re-run tts/all, it overwrites" footgun).
        if _count(config.DIR_AUDIO, "audio_*.mp3") >= len(SCENES) and not force:
            print(f"[v2] tts: {len(SCENES)} clips already in raw_audio/ - skipping "
                  f"(pass 'force' to re-synthesize the voice).")
        else:
            outs = fish_tts.synth_batch()
            if len(outs) != len(SCENES):
                sys.exit(f"[v2] TTS produced {len(outs)}/{len(SCENES)}")
    if stage in ("timing", "all"):
        dur_mod.build()                       # durations are cheap + must track audio
        if stage == "all" and _count(config.DIR_SRT, "srt_*.json") >= len(SCENES) and not force:
            print(f"[v2] timing: {len(SCENES)} srt present - skipping whisper (pass 'force' to redo).")
        else:
            transcribe.transcribe_batch()
    scenes = build_all() if stage in ("build", "all") else sorted(glob.glob(os.path.join(config.DIR_SCENE, "scene_*.html")))
    if stage in ("preview", "all"):
        preview_mod.build(names=[s[0] for s in SCENES])
    if stage in ("cover", "all"):
        render_covers()
    if stage in ("chapters", "all"):
        write_chapters()
    if stage in ("render", "all"):
        workers = int(rest[0]) if rest and rest[0].isdigit() else None  # e.g. python build_v2.py render 2
        render.render_timeline(scenes, _durs(), num_workers=workers)
    # NOTE: render writes a SILENT video track (output/video_track.mp4, -an by
    # design). The sound lives in output/final_output.mp4, produced by muxing
    # narration + ducked BGM here. `render` now falls through to merge too, so a
    # render run never leaves you with a soundless file.
    if stage in ("merge", "render", "all"):
        audio = merge.concat_audio()
        merge.mux(os.path.join(config.DIR_OUTPUT, "video_track.mp4"), audio)  # BGM auto (config.BGM_PATH exists)
        print("[v2] DONE -> output/final_output.mp4 (with narration + BGM)")
    if stage in ("verify", "all"):
        cleanup_mod.verify()
    if stage == "cleanup":
        cleanup_mod.cleanup()
    if stage == "ship":
        if cleanup_mod.verify():
            cleanup_mod.cleanup()
            print("[v2] shipped: deliverables verified, temps cleaned.")
        else:
            sys.exit("[v2] ship aborted: deliverables not ready (run render/merge first).")


if __name__ == "__main__":
    main()
