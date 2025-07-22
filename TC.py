import warnings
import paho.mqtt.client as mqtt
import os
import time
import random
import subprocess

# Suppress DeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)

# MQTT Server Information
MQTT_BROKER = "knewb.info"
MQTT_PORT = 8001
MQTT_TOPIC_TC = "Main_EVO_BLJ/tc/"
MQTT_USERNAME = "MQTT@@##admin"
MQTT_PASSWORD = "MQTT@@##admin"

# Initialize global variables
table_name_dict = {}
selected_table = None
matching_tables = []
blacklist = []  # Blacklist for unmatched tables
written_table = False
selected_table_tc_value = None
selected_table_card_data = []

# File paths
matched_table_path = os.path.join("matched_table_name.txt")
card_path = os.path.join("card.txt")
increment_path = os.path.join("increment.txt")
trigger_path = os.path.join("trigger.txt")
minimum_bet_path = os.path.join("minimum_bet.txt")
blackjack_titles_path = os.path.join("blackjack_titles.txt")

# ===================================================================================== #

# Clear files at program start
for path in [matched_table_path, card_path, trigger_path, minimum_bet_path]:
    with open(path, "w") as file:
        file.write("")

# Load blackjack titles and their mappings
table_mapping = {}
if os.path.exists(blackjack_titles_path):
    with open(blackjack_titles_path, "r") as file:
        for line in file:
            if "<|>" in line:
                original, mapped = line.strip().split("<|>")
                table_mapping[original.strip()] = mapped.strip()
else:
    print(f"Error: {blackjack_titles_path} not found.")
    exit(1)

# Get user input
try:
    tc_threshold = float(input(f"{'Please enter the True Count Value':<35} : "))
    with open("ptc.txt", "w") as file:
        file.write(str(tc_threshold))

    increment_unit = float(input(f"{'Please enter the Increment Unit':<35} : "))
    with open("increment.txt", "w") as file:
        file.write(str(increment_unit))

    minimum_bet = float(input(f"{'Please enter the Minimum Bet Unit':<35} : "))
    print("\033[F\033[K" * 3)
    with open("minimum_bet.txt", "w") as file:
        file.write(str(minimum_bet))
except ValueError:
    print("Invalid input. Please enter a numeric value.")
    exit(1)

# ===================================================================================== #

# Callback for MQTT connection
def on_connect(client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC_TC)

# Callback for MQTT message
def on_message(client, userdata, msg):
    global table_name_dict, selected_table, matching_tables, written_table, selected_table_tc_value, selected_table_card_data

    topic = msg.topic
    sstr = msg.payload.decode()

    if topic == MQTT_TOPIC_TC:
        arr = sstr.split("<|>")
        table_name, tc = arr[0], arr[1]
        table_name = table_name.replace("Japanese", "Japan")
        
        try:
            tc_value = float(tc)
        except ValueError:
            print(f"Invalid TC value received: {tc}")
            return

        if tc_value >= tc_threshold and table_name not in matching_tables:
            matching_tables.append(table_name)

    elif topic == table_name_dict.get(selected_table):
        lines = sstr.splitlines()
        clean_card_data = [line.split("<|>", 1)[1] for line in lines]
        selected_table_card_data = clean_card_data

# ===================================================================================== #

# MQTT setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# Main monitoring loop
try:
    while True:
        # Check if matched_table_name.txt is cleared
        if os.path.getsize(matched_table_path) == 0:
            selected_table = None
            written_table = False
            matching_tables = []
            time.sleep(5.0)  # Time window for collecting tables

        # Select and validate table
        if not written_table:  # Ensure only one table is written until cleared
            while matching_tables:
                candidate_table = random.choice(matching_tables)
                if candidate_table in blacklist:
                    matching_tables.remove(candidate_table)  # Skip blacklisted tables
                    continue

                if candidate_table in table_mapping:
                    selected_table = candidate_table
                    written_table = True

                    # 获取映射值
                    mapped_value = table_mapping.get(selected_table, "Unknown")

                    # 写入 matched_table_name.txt
                    with open(matched_table_path, "w") as file:
                        file.write(f"{selected_table} <|> {mapped_value}\n")

                    print(f"{selected_table} <|> {mapped_value}")

                    # Launch BJ.py
                    subprocess.Popen(["python", "BJ.py"])

                    MQTT_TOPIC_cards = f"Main_EVO_BLJ/cards/{selected_table}/"
                    table_name_dict[selected_table] = MQTT_TOPIC_cards
                    client.subscribe(MQTT_TOPIC_cards)
                    break
                else:
                    blacklist.append(candidate_table)  # Add to blacklist if not valid
                    matching_tables.remove(candidate_table)

        # Monitor trigger.txt
        with open(trigger_path, "r") as file:
            trigger_content = file.read().strip()

        if trigger_content:
            if selected_table_card_data:
                # Write card data to file
                with open(card_path, "w") as file:
                    file.writelines(f"{line}\n" for line in selected_table_card_data)
            else:
                print("No card data available to write.")

            # Clear trigger.txt after processing
            time.sleep(2)
            with open(trigger_path, "w") as file:
                file.write("")

        time.sleep(1)
except KeyboardInterrupt:
    print("Disconnecting...")
finally:
    client.loop_stop()
    client.disconnect()
