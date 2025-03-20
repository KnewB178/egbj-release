import re
import os
import ssl
import time
import json
import random
import string
import asyncio
import aiofiles
import websockets
import subprocess
from datetime import datetime

ssl_context = ssl._create_unverified_context()  

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Sec-WebSocket-Version": "13",
}

# ANSI 转义序列颜色定义
RED = "\033[31m"
BLUE = "\033[34m"
GREEN = '\033[92m'
RESET = "\033[0m"
            
# 设置工作目录为当前脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 声明全局变量
player_id = None
bet_amount = None
minimum_bet = 0.0
seat_taken = False
chosen_seat = None  
game_started = False 
last_tc_value = None
bet_confirmed = False
bj_main_min_bet = None
scores_printed = False
seat_check_attempts = 0
decision_locked = False
last_dealt_cards = None
last_dealer_score = None
last_player_score = None  
decision_offer_retrieved = False
default_table_name = "Default Table"

# ===================================================================================== #
#                               监听并接收 WebSocket 消息                                
# ===================================================================================== #
async def listen_to_blackjack(blackjack_url):
    global bj_main_min_bet, seat_taken, game_started, chosen_seat, bet_confirmed, last_player_score, decision_locked
    awaiting_final_game_result = False

    try:
        with open("matched_table_name.txt", "r") as file:
            matched_table_content = file.read().strip()
        if "<|>" not in matched_table_content or not matched_table_content.split("<|>")[-1].strip():
            print("Invalid mapping in 'matched_table_name.txt'. Closing connection.")
            return await unsubscribe_and_clear_files(websocket)
    except FileNotFoundError:
        print("Error: matched_table_name.txt not found. Closing connection.")
        return await unsubscribe_and_clear_files(websocket)
    except Exception as e:
        print(f"Error processing matched_table_name.txt: {e}")
        return await unsubscribe_and_clear_files(websocket)

    async with websockets.connect(blackjack_url, ssl=ssl_context, extra_headers=HEADERS) as websocket:
        print("\nConnected to Evolution Gaming Server")

        try:
            asyncio.create_task(send_heartbeat(websocket))
            while True:
                if decision_locked:
                    await asyncio.sleep(1)
                    continue
                try:
                    response = await websocket.recv()
                    response_data = json.loads(response)

                    if "subscribe" in response_data and response_data["subscribe"].get("status") == "success":
                        channel = response_data["subscribe"].get("channel")
                        if channel:
                            with open("matched_table_name.txt", "r") as file:
                                matched_table_content = file.read().strip()
                                table_name = matched_table_content.split("<|>")[0].strip()
                            print(f"Subscribed to {table_name}")

                    if response_data.get("type") == "blackjack.v3.seats":
                        seats_info = response_data["args"]["seats"]
                        await enter_seat_module(seats_info, websocket)

                    if response_data.get("type") == "blackjack.v3.tableSettings" and bj_main_min_bet is None:
                        bj_main_min_bet = response_data["args"]["limits"].get("bj-main", {}).get("min")
                        if bj_main_min_bet is not None:
                            print(f"Table Minimum Bet Amount {bj_main_min_bet}")

                    if seat_taken and response_data.get("type") == "blackjack.v3.phase" and response_data["args"].get("name") == "BetsOpen":
                        game_id = response_data["args"].get("gameId")
                        extended_betting_time = response_data["args"].get("extendedBettingTime", False)
                        if game_id:
                            print(f"{'Game ID':<13} : {game_id}")
                            game_started = True
                            bet_confirmed = False
                            if extended_betting_time:
                                print("\nUnsubscribe channel due to shuffling")
                                await leave_seat_module(websocket, chosen_seat)
                                await unsubscribe_and_disconnect(websocket)
                            else:
                                if await check_true_count(websocket):
                                    await submit_bet(websocket, chosen_seat, game_id)
                                    asyncio.create_task(wait_for_bet_confirmation(websocket, chosen_seat))

                    if game_started and response_data.get("type") == "balanceUpdated":
                        balance_info = response_data["args"]
                        balance = balance_info.get("balance")
                        currency_symbol = balance_info.get("currencySymbol")
                        if balance is not None and currency_symbol:
                            print(f"{'Balance':<13} : {balance} {currency_symbol}")

                    if response_data.get("type") == "blackjack.v3.playerChips" and not bet_confirmed:
                        confirmed_bets = response_data["args"].get("confirmed", {})
                        if str(chosen_seat) in confirmed_bets:
                            confirmed_seat_bets = confirmed_bets[str(chosen_seat)]
                            if confirmed_seat_bets:
                                current_time = datetime.now().strftime('%H:%M:%S')
                                print(f"{'Bets Status':<13} : Accepted at {GREEN}{current_time}{RESET}")
                                bet_confirmed = True

                    if game_started and response_data.get("type") == "blackjack.v3.phase" and response_data["args"].get("name") == "Insurance":
                        game_id = response_data["args"].get("gameId")
                        await enter_insurance_module(websocket, game_id)

                    if response_data.get("type") == "blackjack.v3.game":
                        seats_data = response_data["args"].get("seats", {})
                        dealer_data = response_data["args"].get("dealer", {})
                        if str(chosen_seat) in seats_data:
                            first_data = seats_data[str(chosen_seat)].get("first", {})
                            second_data = seats_data[str(chosen_seat)].get("second", {})

                            if "decisionOffer" in first_data:
                                decision_locked = True
                                early_cash_out_rate = first_data["decisionOffer"].get("earlyCashOutRate")
                                await extract_card_data(response_data, chosen_seat)
                                subprocess.run(["python", os.path.join("EV.py")])
                                if early_cash_out_rate is not None:
                                    adjusted_cash_out_rate = early_cash_out_rate - 1
                                    with open("Best_Strategy.txt", "a") as file:
                                        file.write(f"Cash Out = {adjusted_cash_out_rate:.2f}\n")
                                sorted_probabilities = await extract_sorted_probabilities(file_path="Best_Strategy.txt")
                                decisions = first_data["decisionOffer"].get("decisions", [])
                                decision = None
                                for prob in sorted_probabilities:
                                    if prob[0] in decisions:
                                        decision = prob[0]
                                        break
                                await submit_decision(websocket, response_data["args"]["gameId"], first_data["decisionOffer"]["id"], decision, chosen_seat)
                                decision_locked = False

                            if "decisionOffer" in second_data:
                                decision_locked = True
                                early_cash_out_rate = second_data["decisionOffer"].get("earlyCashOutRate")
                                await extract_card_data(response_data, chosen_seat)
                                subprocess.run(["python", os.path.join("EV.py")])
                                if early_cash_out_rate is not None:
                                    adjusted_cash_out_rate = early_cash_out_rate - 1
                                    with open("Best_Strategy.txt", "a") as file:
                                        file.write(f"Cash Out = {adjusted_cash_out_rate:.2f}\n")
                                sorted_probabilities = await extract_sorted_probabilities(file_path="Best_Strategy.txt")
                                decisions = second_data["decisionOffer"].get("decisions", [])
                                decision = None
                                for prob in sorted_probabilities:
                                    if prob[0] in decisions:
                                        decision = prob[0]
                                        break
                                await submit_decision(websocket, response_data["args"]["gameId"], second_data["decisionOffer"]["id"], decision, chosen_seat)
                                decision_locked = False

                    if response_data.get("type") == "blackjack.v3.phase" and response_data["args"].get("name") == "GameResult":
                        if bet_confirmed:
                            await settle_game_result(websocket)

                except websockets.ConnectionClosed:
                    print("WebSocket Connection closed normally\n")
                    await asyncio.sleep(5)
                    os.system('cls' if os.name == 'nt' else 'clear')
                    with open("matched_table_name.txt", "w") as file:
                        file.write("")
                    with open("card.txt", "w") as file:
                        file.write("")
                    break
        except Exception as e:
            print(f"Error occurred: {e}")

# ===================================================================================== #
#                                     主逻辑 main1                                       
# ===================================================================================== #
async def main1():
    if not os.path.exists("roulette_url.txt"):
        with open("roulette_url.txt", "w") as file:
            file.write("wss://example.com/public/blackjack/player/game/DefaultTableID/socket?"
                       "messageFormat=json&EVOSESSIONID=some_session&client_version=1.0&instance=instance1")

    with open("roulette_url.txt", "r") as file:
        blackjack_url = file.read().strip()

    if not os.path.exists("matched_table_name.txt"):
        with open("matched_table_name.txt", "w") as file:
            file.write("Default Table <|> DefaultTableID")

    with open("matched_table_name.txt", "r") as file:
        matched_table_content = file.read().strip()
        blackjack_table_id = matched_table_content.split("<|>")[-1].strip()

    try:
        domain_match = re.match(r"wss://([^/]+)/", blackjack_url)
        if not domain_match:
            raise ValueError("Invalid WebSocket URL format in 'roulette_url.txt'.")
        domain = domain_match.group(1)

        evo_session_id = re.search(r"EVOSESSIONID=([^&]+)", blackjack_url).group(1)
        client_version = re.search(r"client_version=([^&]+)", blackjack_url).group(1)
        instance_id = re.search(r"instance=([^&]+)", blackjack_url).group(1).split('-')[0]
    except Exception as e:
        print(f"Error parsing WebSocket URL: {e}")
        return

    global player_id
    player_id = evo_session_id.split("-")[0]

    blackjack_url = (
        f"wss://{domain}/public/blackjack/player/game/{blackjack_table_id}/socket?"
        f"messageFormat=json&EVOSESSIONID={evo_session_id}&"
        f"instance={instance_id}-{player_id}-{blackjack_table_id}&"
        f"client_version={client_version}"
    )

    await listen_to_blackjack(blackjack_url)

# ===================================================================================== #
#                                     主逻辑 main2                                       
# ===================================================================================== #
async def main2():
    if not os.path.exists("roulette_url.txt"):
        with open("roulette_url.txt", "w") as file:
            file.write("wss://example.com/public/blackjack/player/game/DefaultTableID/socket?"
                       "messageFormat=json&EVOSESSIONID=some_session&client_version=1.0&instance=instance1")

    with open("roulette_url.txt", "r") as file:
        blackjack_url = file.read().strip()

    if not os.path.exists("matched_table_name.txt"):
        with open("matched_table_name.txt", "w") as file:
            file.write("Default Table <|> DefaultTableID:defaultConfig")

    with open("matched_table_name.txt", "r") as file:
        matched_table_content = file.read().strip()
        table_parts = matched_table_content.split("<|>")[-1].strip().split(":")
        blackjack_table_id = table_parts[0]
        table_config = table_parts[1] if len(table_parts) > 1 else "defaultConfig"

    try:
        domain_match = re.match(r"wss://([^/]+)/", blackjack_url)
        if not domain_match:
            raise ValueError("Invalid WebSocket URL format in 'roulette_url.txt'.")
        domain = domain_match.group(1)

        evo_session_id = re.search(r"EVOSESSIONID=([^&]+)", blackjack_url).group(1)
        client_version = re.search(r"client_version=([^&]+)", blackjack_url).group(1)
        instance_match = re.search(r"instance=([^-&]+)-", blackjack_url)
        instance_prefix = instance_match.group(1) if instance_match else "defaultPrefix"
    except Exception as e:
        print(f"Error parsing WebSocket URL: {e}")
        return

    global player_id
    player_id = evo_session_id.split("-")[0]

    blackjack_url = (
        f"wss://{domain}/public/blackjack/player/game/{blackjack_table_id}/socket?"
        f"messageFormat=json&tableConfig={table_config}&EVOSESSIONID={evo_session_id}&"
        f"instance={instance_prefix}-{player_id}-{table_config}&"
        f"client_version={client_version}"
    )

    await listen_to_blackjack(blackjack_url)

# ===================================================================================== #
#                                     心跳发送函数                                        
# ===================================================================================== #
async def send_heartbeat(websocket):
    try:
        while not websocket.closed:
            ping_message = {
                "id": generate_random_id(),
                "type": "metrics.ping",
                "args": {"t": int(time.time() * 1000)}
            }
            await websocket.send(json.dumps(ping_message))
            await asyncio.sleep(5)
    except websockets.exceptions.ConnectionClosedOK:
        print("WebSocket connection closed")
    except websockets.exceptions.ConnectionClosedError as e:
        print("WebSocket connection error")
    except Exception as e:
        print(f"Unexpected error in send_heartbeat : {e}")
    finally:
        pass

# ===================================================================================== #
#                                       桌位模块                                        
# ===================================================================================== #
async def enter_seat_module(seats_info, websocket):
    global bj_main_min_bet, seat_taken, chosen_seat, seat_check_attempts, player_id

    if seat_taken:
        return

    if chosen_seat is not None:
        if str(chosen_seat) in seats_info:
            seat_player_id = seats_info[str(chosen_seat)].get("playerId")
            if seat_player_id and seat_player_id in player_id:
                print(f"Successfully seated at {chosen_seat}\n")
                seat_taken = True
                seat_check_attempts = 0
                return
            else:
                seat_check_attempts += 1
                if seat_check_attempts >= 3:
                    print("No Available Seats")
                    await unsubscribe_and_disconnect(websocket)
                    return

    all_seats = set(range(7))
    occupied_seats = set(int(seat) for seat in seats_info.keys())
    empty_seats = sorted(all_seats - occupied_seats)

    if empty_seats:
        chosen_seat = random.choice(empty_seats)
        take_seat_message = {
            "id": generate_random_id(),
            "type": "blackjack.v3.takeSeat",
            "args": {
                "seat": chosen_seat,
                "copyBets": ["bj-main"]
            }
        }
        await websocket.send(json.dumps(take_seat_message))
    else:
        print("Unsubscribe due to no available seats")
        await unsubscribe_and_disconnect(websocket)

# ===================================================================================== #
#                                     生成随机ID函数                                    
# ===================================================================================== #
def generate_random_id(length=10):                                                                    
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# ===================================================================================== #
#                                     离开桌位模块                                       
# ===================================================================================== #
async def leave_seat_module(websocket, seat_number):
    try:
        leave_seat_message = {
            "id": generate_random_id(),
            "type": "blackjack.v3.leaveSeat",
            "args": {
                "seat": seat_number
            }
        }
        await websocket.send(json.dumps(leave_seat_message))
    except Exception as e:
        print(f"Error leaving seat {seat_number}: {e}")

# ===================================================================================== #
#                                       取消订阅模块                                    
# ===================================================================================== #
async def unsubscribe_and_disconnect(websocket):
    unsubscribe_request = {
        "id": generate_random_id(),
        "type": "connection.unsubscribe",
        "args": {}
    }
    await websocket.send(json.dumps(unsubscribe_request))
    await asyncio.sleep(5)
    await websocket.close()

# ===================================================================================== #
#                                       TC 对比                                        #
# ===================================================================================== #
async def check_true_count(websocket):
    global bet_amount, last_tc_value, last_dealt_cards

    RED = "\033[31m"
    RESET = "\033[0m"

    trigger_path = "trigger.txt"
    with open(trigger_path, "w") as file:
        file.write("trigger")

    await asyncio.sleep(1)

    try:
        card_file_path = "card.txt"

        with open("increment.txt", "r") as increment_file:
            increment = float(increment_file.read().strip())

        with open("minimum_bet.txt", "r") as minimum_bet_file:
            minimum_bet = float(minimum_bet_file.read().strip())

        valid_cards = {"A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"}

        with open(card_file_path, "r") as f:
            lines = f.readlines()

        rc = 0
        total_dealt_cards = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            cards = line.split("<|>")
            for card in cards:
                if card in valid_cards:
                    total_dealt_cards += 1
                    if card in ["2", "3", "4", "5", "6"]:
                        rc += 1
                    elif card in ["T", "J", "Q", "K", "A"]:
                        rc -= 1

        if total_dealt_cards > 270:
            print(f"{RED}Dealt cards exceed 270! Unsubscribing immediately. Total dealt cards: {total_dealt_cards}{RESET}")
            await leave_seat_module(websocket, chosen_seat)
            await unsubscribe_and_disconnect(websocket)
            return False

        total_cards_in_deck = 52 * 8
        remaining_cards = total_cards_in_deck - total_dealt_cards
        remaining_decks = remaining_cards / 52

        tc_value = rc / remaining_decks if remaining_decks > 0 else rc

        if last_dealt_cards == total_dealt_cards:
            print(f"{RED}Dealt cards not update!{RESET}")
            await leave_seat_module(websocket, chosen_seat)
            await unsubscribe_and_disconnect(websocket)
            return False

        last_dealt_cards = total_dealt_cards

        with open("ptc.txt", "r") as ptc_file:
            ptc_value = float(ptc_file.read().strip())

        if tc_value >= ptc_value:
            rounded_tc_value = round(tc_value)
            print(f"{'TC Value':<13} : {tc_value} [ {total_dealt_cards} ]")

            if rounded_tc_value > 5:
                print(f"{RED}Warning: Rounded TC Value exceeds 5! Current Rounded TC: {rounded_tc_value}{RESET}")

            if rounded_tc_value > 10:
                print(f"{RED}Critical: Rounded TC Value exceeds 10! Current Rounded TC: {rounded_tc_value}. No bets will be placed.{RESET}")
                return False

            bet_amount = increment * minimum_bet * (rounded_tc_value - 1) + minimum_bet
            return True
        else:
            print("\nUnsubscribe channel due to TC not match")
            await leave_seat_module(websocket, chosen_seat)
            await unsubscribe_and_disconnect(websocket)
            return False

    except Exception as e:
        print(f"Error reading or comparing values: {e}")
        await unsubscribe_and_disconnect(websocket)
        return False

# ===================================================================================== #
#                                   提交下注请求                                        
# ===================================================================================== #
async def submit_bet(websocket, chosen_seat, game_id):
    global bet_amount, bet_request_time
    try:
        await asyncio.sleep(random.uniform(3, 5))

        bet_request_time = datetime.now()

        bet_message = {
            "id": generate_random_id(),
            "type": "blackjack.v3.chipAction",
            "args": {
                "action": "chip",
                "chips": [{"seat": chosen_seat, "amount": bet_amount, "type": "bj-main"}],
                "gameId": game_id,
                "betTags": {
                    "mwLayout": "8",
                    "openMwTables": "1",
                    "appVersion": "5",
                    "orientation": "landscape",
                    "btVideoQuality": "HIGH",
                    "videoProtocol": "undefined",
                    "btTableView": "0",
                    "latency": 190,
                    "seats": 1
                },
                "correlationId": generate_random_id()
            }
        }
        await websocket.send(json.dumps(bet_message))
        print(f"{'Bet Amount':<13} : {bet_amount}")

    except Exception as e:
        print(f"Error submitting bet: {e}")

# ===================================================================================== #
#                                   下注超时检测                                        
# ===================================================================================== #
async def wait_for_bet_confirmation(websocket, chosen_seat):
    try:
        await asyncio.sleep(20)
        if not bet_confirmed:
            print("Bet confirmation failed ( 20 seconds )")
            await unsubscribe_and_disconnect(websocket)
    except Exception as e:
        print(f"Error in timeout handler: {e}")

# ===================================================================================== #
#                                        保险模块                                        
# ===================================================================================== #
async def enter_insurance_module(websocket, game_id):
    try:
        with open("hands_vertical.txt", "w") as file:
            file.write("A")

        subprocess.run(["python", os.path.join("EV.py")], check=True)

        strategy_file_path = "Best_Strategy.txt"
        if not os.path.exists(strategy_file_path):
            print(f"Error: {strategy_file_path} does not exist.")
            return None

        insurance_ev_value = None
        with open(strategy_file_path, "r") as file:
            for line in file:
                if line.startswith("Insurance EV"):
                    insurance_ev_value = float(line.split("=")[1].strip())
                    break

        if insurance_ev_value is None:
            print("Error: Insurance EV value not found in Best_Strategy.txt")
            return None

        print(f"{'Insurance EV':<13} : {insurance_ev_value}")

        await asyncio.sleep(random.uniform(2, 3))

        insure = insurance_ev_value > 0

        insurance_message = {
            "id": generate_random_id(),
            "type": "blackjack.v3.insurance",
            "args": {
                "gameId": game_id,
                "insure": insure,
                "betTags": {
                    "mwLayout": "8",
                    "openMwTables": "1",
                    "appVersion": "5",
                    "orientation": "landscape",
                    "btVideoQuality": "HIGH",
                    "videoProtocol": "undefined",
                    "btTableView": "0",
                    "latency": 191,
                    "seats": 1
                }
            }
        }

        await websocket.send(json.dumps(insurance_message))

        while True:
            response = await websocket.recv()
            response_data = json.loads(response)
            if response_data.get("type") == "blackjack.v3.requestResult" and response_data["args"].get("name") == "Insurance":
                print(f"{'Decision':<13} : {'Insurance Policy' if insurance_message['args']['insure'] else 'No Insurance Policy'}")
                break

    except Exception as e:
        print(f"Error in enter_insurance_module: {e}")

# ===================================================================================== #
#                                        点数处理                                        
# ===================================================================================== #
async def extract_card_data(response_data, seat_id):
    try:
        dealer_data = response_data.get("args", {}).get("dealer", {})
        dealer_cards = dealer_data.get("cards", [])
        dealer_first_card = dealer_cards[0].get("value", "")[0] if dealer_cards and isinstance(dealer_cards[0], dict) else None

        seats_data = response_data.get("args", {}).get("seats", {})
        player_data = seats_data.get(str(seat_id), {}).get("first", None) or seats_data.get(str(seat_id), {}).get("second", {})
        player_cards = [card.get("value", "")[0] for card in player_data.get("cards", []) if "value" in card]

        if dealer_data.get("hardScore") is not None and dealer_data.get("score") is not None:
            if dealer_data["hardScore"] != dealer_data["score"]:
                dealer_display_score = f"{dealer_data['hardScore']}/{dealer_data['score']}"
            else:
                dealer_display_score = str(dealer_data["score"])
        else:
            dealer_display_score = str(dealer_data.get("score", dealer_data.get("hardScore", "未知")))

        if player_data.get("hardScore") is not None and player_data.get("score") is not None:
            if player_data["hardScore"] != player_data["score"]:
                player_display_score = f"{player_data['hardScore']}/{player_data['score']}"
            else:
                player_display_score = str(player_data["score"])
        else:
            player_display_score = str(player_data.get("score", player_data.get("hardScore", "未知")))

        print(f"{'Score':<13} : {RED}{dealer_display_score}{RESET}   <|>   {BLUE}{player_display_score}{RESET}\n")

        file_path = "hands_vertical.txt"
        async with aiofiles.open(file_path, mode="w") as file:
            if dealer_first_card:
                await file.write(dealer_first_card + "\n")
            for card in player_cards:
                await file.write(card + "\n")

        return dealer_first_card, player_cards

    except Exception as e:
        print(f"提取数据时发生错误: {e}")
        return None, []

# ===================================================================================== #
#                                    解析决策EV值                                        
# ===================================================================================== #
async def extract_sorted_probabilities(file_path="Best_Strategy.txt"):
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"{file_path} not found.")

        decision_mapping = {
            "Hard Hit": "hit",
            "Hard Stand": "stand",
            "Hard Double": "double",
            "Split": "split",
            "Soft Hit": "hit",
            "Soft Stand": "stand",
            "Soft Double": "double",
            "Cash Out": "earlycashout",
            "Insurance ev": "insure",
        }

        probabilities = []
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()
                if "=" in line and any(char.isdigit() for char in line):
                    key, value = line.split("=")
                    key = key.strip()
                    value = float(value.strip())
                    simplified_key = decision_mapping.get(key, key)
                    probabilities.append((simplified_key, value))

        probabilities.sort(key=lambda x: x[1], reverse=True)

        for idx, (key, value) in enumerate(probabilities, start=1):
            print(f"{f'EV Value_{idx}':<13} : {key:<13} | {value}")

        return probabilities

    except Exception as e:
        print(f"Error in extract_sorted_probabilities: {e}")
        raise

# ===================================================================================== #
#                                       决策提交请求                                    
# ===================================================================================== #
async def submit_decision(websocket, game_id, decision_id, decision, chosen_seat):
    await asyncio.sleep(random.uniform(5, 6))

    global decision_locked
    try:
        decision_message = {
            "id": generate_random_id(),
            "type": "blackjack.v3.decision",
            "args": {
                "gameId": game_id,
                "id": decision_id,
                "decision": decision,
                "seat": chosen_seat,
                "preDecision": False,
                "tags": {
                    "mwLayout": "8",
                    "openMwTables": "1",
                    "appVersion": "5",
                    "orientation": "landscape",
                    "btVideoQuality": "HIGH",
                    "videoProtocol": "undefined",
                    "btTableView": "0",
                    "latency": 181,
                    "seats": 1
                }
            }
        }

        print(f"\n{'Submitting':<13} : {decision.capitalize()} for Seat {chosen_seat}")

        retries = 0
        while retries < 1:
            try:
                await websocket.send(json.dumps(decision_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=3)
                response_data = json.loads(response)

                if response_data.get("type") == "blackjack.v3.requestResult":
                    if response_data["args"].get("name") == "Decision":
                        formatted_decision = decision.capitalize()
                        print(f"{'Decision':<13} : {formatted_decision}")
                        decision_locked = False
                        return
            except asyncio.TimeoutError:
                retries += 1
                print("No response received within 3 seconds. Retrying submission...")
                continue

    except Exception as e:
        print(f"Error submitting decision: {e}")

# ===================================================================================== #
#                                  结算模块，处理最终游戏结果                                
# ===================================================================================== #
async def settle_game_result(websocket):
    try:
        while True:
            response = await websocket.recv()
            response_data = json.loads(response)

            if response_data.get("type") == "blackjack.v3.game":
                dealer_data = response_data["args"].get("dealer", {})
                seats_data = response_data["args"].get("seats", {})

                if str(chosen_seat) in seats_data:
                    player_data = seats_data[str(chosen_seat)].get("first", {})

                    if player_data.get("state") == "Final":
                        dealer_score = dealer_data.get("score", "N/A")
                        player_score = player_data.get("score", "N/A")
                        print(f"{'Game Result':<13} : {RED}{dealer_score}{RESET}   <|>   {BLUE}{player_score}{RESET}\n")
                        print('============================================\n')
                        break
    except Exception as e:
        print(f"Error in settle_game_result: {e}")

# ===================================================================================== #
#                       读取 matched_table_name.txt 判断执行主函数                        
# ===================================================================================== #
def select_main():
    try:
        with open("matched_table_name.txt", "r") as file:
            matched_table_content = file.read().strip()

        if ":" in matched_table_content:
            return main2
        else:
            return main1

    except FileNotFoundError:
        print("Error: File not found. Defaulting to main1().")
        return main1

# ===================================================================================== #
#                                   运行主函数                                          
# ===================================================================================== #
if __name__ == "__main__":
    try:
        main_function = select_main()
        asyncio.run(main_function())
    except Exception as e:
        print(f"\nUnexpected error occurred : \n{e}")

        try:
            with open("matched_table_name.txt", "w") as file:
                file.write("")
        except Exception as e:
            print(f"Error clearing : {e}")

        exit(1)
