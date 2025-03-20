import os
import ssl
import json
import certifi
import asyncio
import websockets
import subprocess
from urllib.parse import urlparse, parse_qs

# ===================================================================================== #
#                                  设置 SSL 证书上下文                                     
# ===================================================================================== #
cafile = certifi.where()	# 获取系统证书路径
ssl_context = ssl._create_unverified_context()	# 创建不验证证书的 SSL 上下文
# ===================================================================================== #

# ===================================================================================== #
#                                  添加 WebSocket 必需的 headers                          
# ===================================================================================== #
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",	# 浏览器标识
    "Sec-WebSocket-Version": "13"	# WebSocket 协议版本
}
# ===================================================================================== #

# ===================================================================================== #
#                           获取当前脚本所在目录，确保路径正确                           
# ===================================================================================== #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))	# 获取脚本所在目录
# ===================================================================================== #



# ===================================================================================== #
#                              生成新的 WebSocket URL                                    
# ===================================================================================== #
def generate_new_url(original_url):	# 根据原始 WebSocket URL 生成新的 URL
    parsed_url = urlparse(original_url)	# 解析原始 URL
    query_params = parse_qs(parsed_url.query)	# 解析查询参数

    evo_session_id_full = query_params.get("EVOSESSIONID", [None])[0]	# 获取 EVOSESSIONID
    client_version = query_params.get("client_version", [None])[0]	# 获取 client_version
    instance = query_params.get("instance", [None])[0]	# 获取 instance 参数

    if not all([evo_session_id_full, client_version, instance]):	# 检查参数完整性
        raise ValueError("Missing required parameters in the URL.")	# 缺少必要参数抛出异常

    evo_session_id_short = evo_session_id_full[:16]	# 截取短的 EVOSESSIONID（前16位）
    instance_prefix = instance.split("-")[0]	# 提取 instance 前缀部分

    new_url = (	# 生成新的 WebSocket 连接 URL
        f"wss://{parsed_url.netloc}/public/lobby/socket/v2/{evo_session_id_short}?"
        f"messageFormat=json&device=Desktop&instance={instance_prefix}-{evo_session_id_short}-&"
        f"features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory&"
        f"EVOSESSIONID={evo_session_id_full}&client_version={client_version}"
    )

    return new_url	# 返回生成的新 URL
# ===================================================================================== #



# ===================================================================================== #
#                               保存 URL 到本地配置文件                                  
# ===================================================================================== #
def save_url_to_config(roulette_url):	# 保存 WebSocket URL 到指定配置文件
    config_file = os.path.join(SCRIPT_DIR, "roulette_url.txt")	# 配置文件路径
    with open(config_file, "w", encoding="utf-8") as f:	# 以写入模式打开文件
        f.write(roulette_url)	# 写入 URL 内容
# ===================================================================================== #



# ===================================================================================== #
#                             连接 WebSocket 获取 Blackjack 牌桌信息                         
# ===================================================================================== #
async def connect_to_lobby(url):	# 异步连接 WebSocket 以获取牌桌信息
    try:
        async with websockets.connect(url, ssl=ssl_context, extra_headers=HEADERS) as websocket:	# 建立 WebSocket 连接
            while True:
                response = await websocket.recv()	# 接收服务器响应
                data = json.loads(response)	# 解析 JSON 数据

                if data.get("type") == "lobby.configs":	# 检查是否为 lobby 配置信息
                    configs = data.get("args", {}).get("configs", {})	# 获取配置项

                    blackjack_titles = [	# 提取所有 speed Blackjack 牌桌
                        (cfg["title"], key) for key, cfg in configs.items()
                        if cfg.get("gt") == "blackjack" and 
                           cfg.get("flags", {}).get("gVariant") == "speed"
                    ]

                    save_blackjack_titles_to_file(blackjack_titles)	# 保存提取到的牌桌信息
                    break	# 完成后跳出循环
    except websockets.exceptions.InvalidStatusCode as e:	# 捕捉 WebSocket 连接失败异常
        print(f"Connection failed with status code : {e.status_code}. URL : {url}")	# 输出失败信息
    except Exception as e:	# 捕捉其他异常
        print(f"An error occurred: {e}")	# 输出异常信息
# ===================================================================================== #



# ===================================================================================== #
#                               保存 Blackjack 牌桌信息到文件                               
# ===================================================================================== #
def save_blackjack_titles_to_file(titles_with_ids):	# 保存牌桌信息及映射
    file_name = os.path.join(SCRIPT_DIR, "blackjack_titles.txt")	# 输出文件路径
    categories = [	# 分类优先级顺序
        "Speed Blackjack",
        "Evo Speed Blackjack",
        "Speed VIP Blackjack",
        "Classic Speed Blackjack",
    ]
    def sort_key(item):	# 自定义排序规则
        title, _ = item
        category_index = next((i for i, cat in enumerate(categories) if title.startswith(cat)), len(categories))	# 匹配分类索引
        if title.startswith("Speed VIP Blackjack"):
            parts = title.rsplit(" ", 1)
            letter_part = parts[-1] if len(parts) > 1 else ""	# 提取字母部分
            return (category_index, letter_part)
        name_parts = title.rsplit(" ", 1)
        number_part = "".join(filter(str.isdigit, name_parts[-1])) if name_parts[-1].isdigit() else "0"	# 提取数字部分
        return (category_index, name_parts[0], int(number_part))
    
    sorted_titles = sorted(titles_with_ids, key=sort_key)	# 按规则排序

    with open(file_name, "w", encoding="utf-8") as file:	# 写入文件
        for title, table_id in sorted_titles:
            lower_title = title.lower()	# 转小写方便匹配
            title = title.replace("Evo Blackjack Tốc Độ", "Evo Speed Blackjack").replace("Evo Blackjack Tốc độ", "Evo Speed Blackjack")	# 越南语处理
            title = title.replace("Blackjack Tốc Độ VIP", "Speed VIP Blackjack").replace("Blackjack Tốc độ VIP", "Speed VIP Blackjack")
            title = title.replace("Blackjack Tốc Độ", "Speed Blackjack").replace("Blackjack Tốc độ", "Speed Blackjack")
            title = title.replace("Blackjack Cổ Điển Tốc Độ", "Classic Speed Blackjack")
            title = title.replace("Evo 스피드 블랙잭", "Evo Speed Blackjack")	# 韩语处理
            title = title.replace("스피드 VIP 블랙잭", "Speed VIP Blackjack")
            title = title.replace("스피드 블랙잭", "Speed Blackjack")
            title = title.replace("코리안 Speed Blackjack", "Korean Speed Blackjack")
            title = title.replace("클래식 Speed Blackjack", "Classic Speed Blackjack")
            title = title.replace("클래식 speed blackjack", "Classic Speed Blackjack")
            title = title.replace("클래식 블랙잭", "Classic Blackjack")
            title = title.replace("클래식Speed Blackjack", "Classic Speed Blackjack")
            title = title.replace("클래식 speed 블랙잭", "Classic Speed Blackjack")
            title = title.replace("Evo Blackjack Kilat", "Evo Speed Blackjack")	# 印尼语处理
            title = title.replace("Blackjack Kilat VIP", "Speed VIP Blackjack")
            title = title.replace("Blackjack Kilat", "Speed Blackjack")
            title = title.replace("Speed Blackjack Nhật Bản", "Japan Speed Blackjack")	# 日语处理
            title = title.replace("Speed Blackjack Japan", "Japan Speed Blackjack")
            title = title.replace("Speed Blackjack Hàn Quốc", "Korean Speed Blackjack")
            title = title.replace("Blackjack Nhanh Nhà Cái Hàn Quốc", "Korean Speed Blackjack (Dealer)")
            file.write(f"{title} <|> {table_id}\n")	# 写入最终结果
# ===================================================================================== #



# ===================================================================================== #
#                               延迟启动 TC.py 确保数据已获取                           
# ===================================================================================== #
async def delayed_start():	# 异步延迟启动函数
    await asyncio.sleep(2)	# 延迟 2 秒等待数据获取完成

    tc_path = os.path.join(SCRIPT_DIR, "TC.py")	# 拼接 TC.py 绝对路径

    if os.path.exists(tc_path):	# 判断 TCC.py 是否存在
        subprocess.Popen(["python", tc_path])	# 启动 TC.py 脚本
    else:
        print(f"Error : File missing")	# 输出错误信息
# ===================================================================================== #



# ===================================================================================== #
#                                   主程序入口及执行流程                                 
# ===================================================================================== #
if __name__ == "__main__":	# 主程序入口
    original_url = input("Enter WebSocket URL : ").strip()	# 获取用户输入的 WebSocket URL
    os.system('cls' if os.name == 'nt' else 'clear')    # 清空屏幕
    save_url_to_config(original_url)	# 保存输入的 URL 到配置文件

    try:
        new_url = generate_new_url(original_url)	# 生成新的 WebSocket URL
        asyncio.run(connect_to_lobby(new_url))	# 连接至 WebSocket 获取牌桌信息
        asyncio.run(delayed_start())	# 延迟启动 TCC.py 脚本
    except ValueError as e:	
        print("Error:", e)	# 捕捉并输出错误信息
# ===================================================================================== #


