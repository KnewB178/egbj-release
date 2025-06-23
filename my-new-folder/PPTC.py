import os
import json
import time
import asyncio
import warnings
import winsound
import threading
import subprocess
import paho.mqtt.client as mqtt

from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from asyncio import to_thread
from rich.layout import Layout
from rich.prompt import Prompt
from rich.console import Console

warnings.filterwarnings("ignore", category=DeprecationWarning)

CONFIG_DIR = r"C:\WindowsOS\PP"
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# ===================================================================================== #
#                                  全局变量区域                                         
# ===================================================================================== #
mqtt_data = {}
tc_threshold = -9
console = Console()
qualified_tables = {}
has_auto_selected = False
selected_table_name = None
custom_panel_override = None
ev2_custom_rendered = False
matched_seat_index = None
matched_seat_score = None
matched_seat_ev = None
is_game_ended = {}

# ===================================================================================== #
#                                保存配置至 config.json                                 
# ===================================================================================== #
def save_settings(tc_threshold, custom_panel_override, cards=None, seat_number=None, dealer_upcard=None, all_cards=None, filename=CONFIG_PATH):
    try:
        # 构建基础数据
        data = {
            "tc_threshold": tc_threshold,
            "custom_panel_override": custom_panel_override
        }
        # 可选字段
        if dealer_upcard is not None:
            data["dealer_upcard"] = dealer_upcard
        if seat_number is not None:
            data["seat_number"] = seat_number
        if cards is not None:
            data["cards"] = cards
        if all_cards is not None:
            data["all_cards"] = all_cards

        # 写入配置文件
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Failed to save {filename}: {e}")

# ===================================================================================== #
#                             加载 True Count 阈值与面板配置                            
# ===================================================================================== #
def load_settings(filename=CONFIG_PATH):
    default_settings = {
        "tc_threshold": 0,
        "custom_panel_override": "MQTT Data"
    }

    if not os.path.exists(filename):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(default_settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Failed to create {filename}: {e}")
        return default_settings

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "tc_threshold": float(data.get("tc_threshold", 0)),
                "custom_panel_override": data.get("custom_panel_override", "MQTT Data")
            }
    except Exception as e:
        print(f"❌ Failed to load {filename}: {e}")
        return default_settings

# ===================================================================================== #
#                                Rich 布局构建函数                                      
# ===================================================================================== #
def build_layout():
    layout = Layout()

    layout.split_row(
        Layout(name="left"),
        Layout(name="right")
    )

    layout["left"].split(
        Layout(name="tc_input", size=3),
        Layout(name="qualified", ratio=1)
    )

    layout["right"].split(
        Layout(name="selection", size=3),
        Layout(name="true_count_value", size=3),
        Layout(name="details", size=26),
        Layout(name="ev_row", size=5),
        Layout(name="cards_panel", size=12)
    )

    layout["ev_row"].split_row(
        Layout(name="ev1"),
        Layout(name="ev2"),
        Layout(name="ev3")
    )

    return layout

# ===================================================================================== #
#                                  MQTT 回调函数                                        
# ===================================================================================== #
def on_message(client, userdata, msg):
    global qualified_tables, selected_table_name, has_auto_selected

    topic = msg.topic
    payload = json.loads(msg.payload.decode())

    # ========== 玩家决策推送（pp/decision/#） ==========
    if "decision" in topic:
        handle_decision_payload(topic, payload)
        return

    # ========== 游戏结束推送（pp/gameend/#） ==========
    if "gameend" in topic:
        table_name = topic.split("/")[-1]
        is_game_ended[table_name] = True
        return

    # ========== 非 table / seat 推送一律忽略 ==========
    if not any(x in topic for x in ["table", "seat", "playerSeat"]):
        return

    table_name = topic.split("/")[-1]

    # ========== 若是 playerSeat 推送，解除灰色状态 ==========
    if topic.startswith("pp/table/"):
        is_game_ended[table_name] = False

    # ========== 抓取 TC 与洗牌标志 ==========
    tc_raw = payload.get("tc")
    try:
        tc = float(tc_raw)
    except (ValueError, TypeError):
        tc = None

    cards = payload.get("cards", [])

    # ========== 洗牌：cards 为空时 ==========
    if isinstance(cards, list) and len(cards) == 0:
        existing_data = mqtt_data.get(table_name, {})
        existing_names = existing_data.get("player_names", {})

        keep_data = custom_panel_override in existing_names.values()

        mqtt_data[table_name] = {
            "player_names": existing_names,
            "tc": 0.0,
            "total": 0 if not keep_data else existing_data.get("total", 0),
            "timestamp": "-" if not keep_data else existing_data.get("timestamp", "-"),
            "dealer": {} if not keep_data else existing_data.get("dealer", {}),
            "players": {} if not keep_data else existing_data.get("players", {}),
            "cards": []
        }

        if selected_table_name == table_name and not keep_data:
            selected_table_name = None

        return

    # ========== 正常记录 MQTT 数据 ==========
    mqtt_data[table_name] = payload

    # ========== 判断是否取消选中：只依赖玩家名是否还在 ==========
    existing_data = mqtt_data.get(table_name, {})
    current_players = existing_data.get("player_names", {})
    if (
        selected_table_name == table_name and
        custom_panel_override not in current_players.values()
    ):
        selected_table_name = None

    # ========== 自动选中匹配玩家名称所在桌（仅首次） ==========
    matching_tables = [
        tname for tname, pdata in mqtt_data.items()
        if custom_panel_override in pdata.get("player_names", {}).values()
    ]

    if not has_auto_selected and len(matching_tables) == 1 and table_name == matching_tables[0]:
        selected_table_name = table_name
        has_auto_selected = True
    elif has_auto_selected and not matching_tables:
        selected_table_name = None
        has_auto_selected = False

    # ========== 左侧筛选用合格表（不会影响右侧显示） ==========
    if tc is not None and tc >= tc_threshold:
        qualified_tables[table_name] = tc
    else:
        qualified_tables.pop(table_name, None)

# ===================================================================================== #
#                             异步用户输入监听函数（带清屏）                           
# ===================================================================================== #
async def input_loop():
    global tc_threshold, selected_table_name, qualified_tables, custom_panel_override

    while True:
        try:
            console.clear()
            user_input = await to_thread(input, "")
        except (KeyboardInterrupt, EOFError):
            break

        user_input = user_input.strip()

        if user_input.startswith("t="):
            try:
                tc_threshold = float(user_input.split("=", 1)[-1])
                qualified_tables.clear()
                selected_table_name = None
                for table, data in mqtt_data.items():
                    if data.get("tc") is not None and data["tc"] >= tc_threshold:
                        qualified_tables[table] = data["tc"]
                save_settings(tc_threshold, custom_panel_override)
            except:
                pass

        elif user_input.startswith("="):
            try:
                index = int(user_input.split("=", 1)[-1])
                keys = list(qualified_tables.keys())
                if 1 <= index <= len(keys):
                    selected_table_name = keys[index - 1]
            except:
                pass

        elif user_input.startswith("p="):
            custom_text = user_input.split("=", 1)[-1].strip()
            custom_panel_override = custom_text if custom_text else None
            save_settings(tc_threshold, custom_panel_override)

# ===================================================================================== #
#                         处理玩家决策推送，保存至 config.json                           
# ===================================================================================== #
def handle_decision_payload(topic, payload):
    global matched_seat_index, matched_seat_score, selected_table_name

    table_name = topic.split("/")[-1]
    seat = payload.get("seatNumber")

    if (
        matched_seat_index is not None and
        seat is not None and
        seat == matched_seat_index and
        table_name == selected_table_name
    ):
        cards = payload.get("cards", [])

        dealer_data = mqtt_data.get(selected_table_name, {}).get("dealer", {}).get("cards", [])
        dealer_upcard = dealer_data[0] if dealer_data else None

        all_cards_raw = mqtt_data.get(selected_table_name, {}).get("cards", [])
        all_cards = ["0" if str(c) == "10" else str(c) for c in all_cards_raw]

        save_settings(
            tc_threshold,
            custom_panel_override,
            cards=cards,
            seat_number=seat,
            dealer_upcard=dealer_upcard,
            all_cards=all_cards
        )

        # 开启新线程运行 EV.py 后再读取结果
        threading.Thread(target=ev_runner_thread).start()

# ===================================================================================== #
#                          EV 脚本执行器：运行 EV.py 并读取结果                         
# ===================================================================================== #
def ev_runner_thread():
    global matched_seat_score, matched_seat_ev
    # 调用指定路径下的 EV.py
    subprocess.Popen(
        ["python", r"C:\WindowsOS\PP\EV.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        evr = data["ev_result"]
        matched_seat_score = evr.get("best", "-")
        matched_seat_ev = evr.get(matched_seat_score.lower(), None)
    except Exception:
        matched_seat_score = "-"
        matched_seat_ev = None

    winsound.MessageBeep()

# ===================================================================================== #
#                              Rich 动态内容刷新函数                                    
# ===================================================================================== #
def update_layout(layout):
    global ev2_custom_rendered, matched_seat_score

    # —— 左上：True Count 阈值显示 —— #
    layout["tc_input"].update(
        Panel(f"🎯 Current True Count Threshold 🎯 : [cyan]{tc_threshold:+.2f}[/cyan]", title="")
    )

    # ✅ 修复关键：不再用 qualified_tables 控制右侧显示
    if not selected_table_name or selected_table_name not in mqtt_data:
        selected_name = "-"
        tc_display = "-"
        issued_display = "-"
    else:
        selected_name = selected_table_name
        data = mqtt_data.get(selected_name, {})
        tc_val = data.get("tc")
        issued_val = data.get("total")
        tc_display = f"{tc_val:+.2f}" if tc_val is not None else "-"
        issued_display = str(issued_val) if issued_val is not None else "-"

    layout["selection"].update(
        Panel(f"💬 Selected Table 💬 : [yellow]{selected_name}[/yellow]", title="")
    )

    # —— 左中：True Count Value 与 Issued Cards —— #
    if selected_name in mqtt_data:
        current_tc = mqtt_data[selected_name].get("tc")
        current_issued = mqtt_data[selected_name].get("total")

        tc_str = (
            f"📊 True Count Value 📊 : [bold green]{current_tc:+.2f}[/bold green]"
            if current_tc is not None else "📊 True Count Value 📊 : [dim]-[/dim]"
        )
        issued_str = (
            f"🂡 Total Issued Cards 🂡 : [bold cyan]{current_issued}[/bold cyan]"
            if current_issued is not None else "🂡 Issued Cards 🂡 : [dim]-[/dim]"
        )
    else:
        tc_str = "📊 True Count Value 📊 : [dim]-[/dim]"
        issued_str = "🂡 Issued Cards 🂡 : [dim]-[/dim]"

    layout["true_count_value"].split_row(
        Layout(Panel(tc_str, title=""), name="tc_half"),
        Layout(Panel(issued_str, title=""), name="issued_half")
    )

    # —— 左侧合格桌列表 —— #
    table = Table(show_header=True, header_style="bold")
    table.add_column(" Index ", justify="center", style="white", width=6)
    table.add_column(" Qualified Blackjack Tables ", justify="center", style="white")
    table.add_column(" TC ", justify="center", style="white")
    table.add_column(" Issued ", justify="center", style="white")
    table.add_column(" Time ", justify="center", style="white")

    for i, (name, val) in enumerate(qualified_tables.items(), start=1):
        # 时间与已发牌数
        time_str = "-"
        issued = "-"
        if name in mqtt_data:
            data = mqtt_data[name]
            timestamp = data.get("timestamp")
            issued_val = data.get("total")
            if timestamp:
                time_str = timestamp.split(" ")[-1] if " " in timestamp else timestamp
            if issued_val is not None:
                issued = str(issued_val)

        # TC 简单格式
        tc_val = mqtt_data.get(name, {}).get("tc")
        tc_str = f"{tc_val:+.2f}" if tc_val is not None else "-"

        # 判断是否有空位
        player_names = mqtt_data.get(name, {}).get("player_names")
        if not isinstance(player_names, dict):
            has_vacancy = True
        else:
            actual_players = [
                v for v in player_names.values()
                if isinstance(v, str) and v.strip()
            ]
            has_vacancy = len(actual_players) < 7

        # 如果有空位，桌名与 TC 同时标记绿色
        if has_vacancy:
            name_cell = f"[green]{name}[/green]"
            tc_cell   = f"[green]{tc_str}[/green]"
        else:
            name_cell = name
            tc_cell   = tc_str

        table.add_row(
            str(i),
            name_cell,
            tc_cell,
            issued,
            time_str
        )

    layout["qualified"].update(Panel(table, title="", border_style="white"))

    # ====== 决策 EV 面板判断 ======
    if custom_panel_override:
        player_names_check = mqtt_data.get(selected_name, {}).get("player_names", {})
        if custom_panel_override in player_names_check.values():
            title_text = f"[bold yellow]{custom_panel_override}[/bold yellow]"
            decision_logic(selected_name, player_names_check, layout)
        else:
            title_text = f"[dim]{custom_panel_override}[/dim]"
            layout["ev2"].update(
                Panel(
                    Align.center(Text("🂫 Pragmatic Play 🂡", style="dim"), vertical="middle"),
                    title=None,
                    border_style="white"
                )
            )
    else:
        title_text = "MQTT Data"
        layout["ev2"].update(
            Panel(
                Align.center(Text("🂫 Pragmatic Play 🂡", style="dim"), vertical="middle"),
                title=None,
                border_style="white"
            )
        )

    # ====== 玩家与庄家明细 ======
    if selected_name in mqtt_data:
        data = mqtt_data[selected_name]
        lines = []
        dealer = data.get("dealer", {})
        d_score = dealer.get("score", "-")
        d_cards = " ".join(
            "0" if str(c) == "10" else str(c)
            for c in dealer.get("cards", [])
        )
        lines.append(f"🧑 {'Dealer':<13}: {d_score:<5} [ {d_cards} ]")

        for key in sorted(data.get("players", {})):
            p = data["players"][key]
            score = p.get("score", "-")
            cards = " ".join(
                "0" if str(c) == "10" else str(c)
                for c in p.get("cards", [])
            )
            display_key = key.replace("_h0", "") if key.endswith("_h0") else key
            label = f"Player {display_key}"
            lines.append(f"🧍 {label:<13}: {score:<5} [ {cards} ]")

        if is_game_ended.get(selected_name):
            lines = [f"[dim]{line}[/dim]" for line in lines]
            layout["ev2"].update(
                Panel(
                    Align.center(Text("🂫 Pragmatic Play 🂡", style="dim"), vertical="middle")
                )
            )
            ev2_custom_rendered = False
            matched_seat_score = "-"

        detail_panel = Panel("\n" + "\n".join(lines), title=title_text)
    else:
        empty_msg = Align.center(
            Text("No data received for this table yet", style="dim"),
            vertical="middle"
        )
        detail_panel = Panel(empty_msg, title=title_text)

    layout["details"].update(detail_panel)

    # ====== 已出牌展示 ======
    if selected_name in mqtt_data:
        raw_cards = mqtt_data[selected_name].get("cards", [])
        converted = [
            "0" if str(c) == "10" else str(c)
            for c in raw_cards
        ]
        MAX_CARDS_PER_LINE = 35
        MAX_LINES = 9
        trimmed = converted[:MAX_CARDS_PER_LINE * MAX_LINES]
        grouped = [
            " ".join(trimmed[i:i + MAX_CARDS_PER_LINE])
            for i in range(0, len(trimmed), MAX_CARDS_PER_LINE)
        ]
        if grouped:
            while len(grouped) < MAX_LINES:
                grouped.append("")
            cards_panel = Panel("\n" + "\n".join(grouped), title="Cards Value")
        else:
            empty_cards = Align.center(
                Text("No cards available", style="dim"),
                vertical="middle"
            )
            cards_panel = Panel(empty_cards, title="Cards Value")
    else:
        empty_cards = Align.center(
            Text("No cards available", style="dim"),
            vertical="middle"
        )
        cards_panel = Panel(empty_cards, title="Cards Value")

    if layout["cards_panel"].renderable != cards_panel:
        layout["cards_panel"].update(cards_panel)

    # 清空 EV 图案（如果未渲染）
    if not ev2_custom_rendered:
        layout["ev2"].update(
            Panel(
                Align.center(Text("🂫 Pragmatic Play 🂡", style="dim"), vertical="middle")
            )
        )
    ev2_custom_rendered = False

    layout["ev1"].update(
        Panel(
            Align.center(Text("🂫 Blackjack 🂡", style="dim"), vertical="middle"),
            title=None,
            border_style="white"
        )
    )
    layout["ev3"].update(
        Panel(
            Align.center(Text("🂫 Blackjack 🂡", style="dim"), vertical="middle"),
            title=None,
            border_style="white"
        )
    )

# ===================================================================================== #
#         决策逻辑：匹配玩家名称并更新 EV 区块（图案和内容随决策一起变色）            
# ===================================================================================== #
def decision_logic(table_name, player_names, layout):
    global ev2_custom_rendered, matched_seat_index, matched_seat_score, matched_seat_ev

    for seat_str, name in player_names.items():
        if name == custom_panel_override:
            seat_number = int(seat_str)
            matched_seat_index = seat_number - 1

            dealer_score = mqtt_data.get(table_name, {}).get("dealer", {}).get("score")
            if dealer_score == "1/11":

                dealer_data = mqtt_data.get(table_name, {}).get("dealer", {}).get("cards", [])
                dealer_upcard = dealer_data[0] if dealer_data else None
                all_cards_raw = mqtt_data.get(table_name, {}).get("cards", [])
                all_cards = ["0" if str(c) == "10" else str(c) for c in all_cards_raw]
                player_data = mqtt_data.get(table_name, {}).get("players", {}).get(seat_str, {})
                player_cards = player_data.get("cards", [])

                save_settings(
                    tc_threshold,
                    custom_panel_override,
                    cards=player_cards,
                    seat_number=seat_number,
                    dealer_upcard=dealer_upcard,
                    all_cards=all_cards
                )
                threading.Thread(target=ev_runner_thread).start()
                time.sleep(0.5)

                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        insurance_ev = float(data.get("insurance_ev", 0))
                    if insurance_ev >= 0:
                        symbol = "🟩"
                        color = "bold green"
                    else:
                        symbol = "🟥"
                        color = "bold red"
                    
                    # 创建两行文本，每行都单独居中
                    line1 = Align.center(Text.from_markup(f"[{color}]{symbol} Insurance {symbol}[/{color}]"))
                    line2 = Align.center(Text.from_markup(f"[{color}][{insurance_ev:+.2f}][/{color}]"))
                    
                    # 将两行组合成一个垂直布局
                    insurance_layout = Layout()
                    insurance_layout.split_column(
                        Layout(line1, size=2),
                        Layout(line2, size=1)
                    )
                    
                    layout["ev2"].update(
                        Panel(insurance_layout)
                    )
                    ev2_custom_rendered = True
                except Exception as e:
                    print(f"[❌ Insurance EV 读取失败] {e}")
                    layout["ev2"].update(
                        Panel(Align.center(Text("🂫 Pragmatic Play 🂡", style="dim"), vertical="middle"))
                    )
                return

            if not matched_seat_score or matched_seat_score == "-":
                layout["ev2"].update(
                    Panel(Align.center(Text("🂫 Pragmatic Play 🂡", style="dim"), vertical="middle"))
                )
            else:
                decision = matched_seat_score.upper()
                if decision == "HIT":
                    color = "bold green"
                    symbol = "🟩"
                elif decision == "STAND":
                    color = "bold red"
                    symbol = "🟥"
                elif decision == "DOUBLE":
                    color = "bold orange3"
                    symbol = "🟧"
                elif decision == "SPLIT":
                    color = "bold deepskyblue1"
                    symbol = "🟦"
                else:
                    color = "bold white"
                    symbol = "⬜"

                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        evr = json.load(f).get("ev_result", {})
                    ev_items = [
                        (dec.upper(), val)
                        for dec, val in evr.items()
                        if dec not in ("type", "best") and isinstance(val, (int, float))
                    ]
                    ev_items.sort(key=lambda x: x[1], reverse=True)
                    ev_items = ev_items[:3]

                    symbol_map = {"HIT": "🟩", "STAND": "🟥", "DOUBLE": "🟧", "SPLIT": "🟦"}

                    lines = []
                    max_dec_length = max(len(dec) for dec, _ in ev_items)  
                    for idx, (dec, val) in enumerate(ev_items):
                        symbol_char = symbol_map.get(dec, '⬜')  
                        ev_str = f"[{val:+.2f}]"
                        
                        if idx == 0:
                            # 第一行：前后都带图标
                            formatted_dec = dec.ljust(max_dec_length)  
                            lines.append(f"[{color}]{symbol_char} {formatted_dec} {ev_str} {symbol_char}[/{color}]")
                        else:
                            # 第二行和第三行：添加空格模拟图标宽度
                            padding = " " * (len(symbol_char) * 2 + 2)  
                            formatted_dec = dec.ljust(max_dec_length)
                            lines.append(f"[dim]{padding}{formatted_dec} {ev_str}[/dim]")

                    debug_text = "\n".join(lines)
                except Exception:
                    ev_str = f"{matched_seat_ev:+.2f}" if matched_seat_ev is not None else ""
                    debug_text = f"{symbol} {matched_seat_score} {f'[ {ev_str} ]' if ev_str else ''} {symbol}"

                layout["ev2"].update(
                    Panel(Align.center(Text.from_markup(debug_text), vertical="middle"))
                )
                ev2_custom_rendered = True

            break

# ===================================================================================== #
#                                 主异步循环函数                                       
# ===================================================================================== #
async def main():
    global tc_threshold, custom_panel_override
    settings = load_settings()
    tc_threshold = float(settings.get("tc_threshold", 0))
    custom_panel_override = settings.get("custom_panel_override", "MQTT Data")

    layout = build_layout()

    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.username_pw_set("MQTT@@##admin", "MQTT@@##admin")
    client.on_message = on_message
    client.connect("knewb.info", 8881, 60)
    client.subscribe("pp/table/#")
    client.subscribe("pp/decision/#")
    client.subscribe("pp/gameend/#")
    client.loop_start()

    asyncio.create_task(input_loop())

    with Live(layout, refresh_per_second=1, screen=True):
        while True:
            update_layout(layout)
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())