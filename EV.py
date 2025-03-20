import numpy as np
import os
import sys

# 初始化数组和变量
num_cards = np.zeros(11, dtype=int)            # 存储牌的计数（索引从1开始，索引0未使用）
decks = None                                   # 等价于VBA中的Variant类型，用于存储牌组数
num_total = None                               # 等价于VBA中的Variant类型，用于存储总牌数
out_cards = np.zeros(12, dtype=int)            # 存储被移除的牌的数量（包括额外索引）

Hard_Bust = np.zeros(32, dtype=float)          # 硬牌爆牌概率数组 # 用于存储硬牌爆牌的概率
Soft_Bust = np.zeros(32, dtype=float)          # 软牌爆牌概率数组 # 用于存储软牌爆牌的概率
p = np.zeros(31, dtype=float)                  # 概率数组 # 用于存储概率值（1到30有效）

Hard_Hand = np.zeros((32, 32), dtype=float)    # 硬牌手概率二维数组 # 用于存储硬牌手概率
Soft_Hand = np.zeros((32, 32), dtype=float)    # 软牌手概率二维数组 # 用于存储软牌手概率
Dealer_Hand = np.zeros((32, 32), dtype=float)  # 庄家手牌概率二维数组 # 用于存储庄家手牌概率
Dealer_Bust = np.zeros(32, dtype=float)        # 庄家爆牌概率数组 # 用于存储庄家爆牌的概率
Dealer_Hand_BJ = np.zeros(11, dtype=float)     # 庄家拿到Blackjack（黑杰克）的概率 # 用于存储庄家黑杰克的概率

P_Hard_S = np.zeros((32, 32), dtype=float)     # 硬牌站立概率二维数组 # 用于存储硬牌站立的概率
P_Soft_S = np.zeros((32, 32), dtype=float)     # 软牌站立概率二维数组 # 用于存储软牌站立的概率

P_Hard_H = np.zeros((32, 32), dtype=float)     # 硬牌要牌概率二维数组 # 用于存储硬牌要牌的概率
P_Soft_H = np.zeros((32, 32), dtype=float)     # 软牌要牌概率二维数组 # 用于存储软牌要牌的概率

P_Hard_HS = np.zeros((32, 32), dtype=float)    # 硬牌要牌/站立概率二维数组 # 用于存储硬牌要牌和站立的综合概率
P_Soft_HS = np.zeros((32, 32), dtype=float)    # 软牌要牌/站立概率二维数组 # 用于存储软牌要牌和站立的综合概率

Temp_Total = None                              # 临时变量 # 用于临时存储计算结果
P_Soft_D = np.zeros((32, 32), dtype=float)     # 软牌双倍概率二维数组 # 用于存储软牌双倍下注的概率
P_Hard_D = np.zeros((32, 32), dtype=float)     # 硬牌双倍概率二维数组 # 用于存储硬牌双倍下注的概率

P_Soft_HSD = np.zeros((32, 32), dtype=float)   # 软牌要牌/站立/双倍概率二维数组 # 用于存储软牌要牌、站立和双倍下注的综合概率
P_Hard_HSD = np.zeros((32, 32), dtype=float)   # 硬牌要牌/站立/双倍概率二维数组 # 用于存储硬牌要牌、站立和双倍下注的综合概率

P_Split = np.zeros((32, 32), dtype=float)      # 分牌概率二维数组 # 用于存储分牌的概率
P_Split_YN = np.zeros((32, 32), dtype=float)   # 分牌决策概率二维数组 # 用于存储是否分牌的决策概率

# ----------------------------------------------------------------------------------------------------------------------------#

decks = 8                                      # 牌组数量（每副牌含52张牌）
num_total = 0                                  # 初始化牌的总数

# 切换当前工作目录到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 使用相对路径读取文件
file_path = "card.txt"

# 检查文件是否存在
if not os.path.exists(file_path):
    print(f"File '{file_path}' does not exist in the current directory!")
else:
    # 打开文件并读取内容
    with open(file_path, "r") as file:
        content = file.read()
        #print("File content:", content)

# ----------------------------------------------------------------------------------------------------------------------------#

# 定义需要统计的点数
valid_cards = ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K']
card_counts = {card: 0 for card in valid_cards}  # 初始化计数

# 分割内容并统计有效点数的出现次数
for card in content.split('<|>'):
    card = card.strip()  # 去掉多余的空格
    if card in card_counts:
        card_counts[card] += 1

# 合并 T, J, Q, K 的出现次数到 T（即 10 点）
card_counts['T'] += card_counts['J'] + card_counts['Q'] + card_counts['K']

# 转换为 out_cards 格式
out_cards = [0] * 11  # 索引 1-10 分别对应 A, 2, 3, ..., 9, T
mapping = {'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10}

for card, index in mapping.items():
    if card == 'T':  # 只保留合并后的 T 的总次数
        out_cards[index] = card_counts['T']
    else:  # 其他点数直接赋值
        out_cards[index] = card_counts[card]

# 打印结果以验证
#print("# 转换后的 out_cards 数据：")
#for i in range(1, 11):  # 索引从 1 开始到 10
    #print(f"out_cards[{i}] = {out_cards[i]}")

# ----------------------------------------------------------------------------------------------------------------------------#

# 计算剩余牌数量和总牌数
for i in range(1, 10):                         # 遍历牌值1到9
    num_cards[i] = decks * 4 - out_cards[i]    # 每个点数的牌有4张，减去移出的牌
    num_total += num_cards[i]                  # 累加到总牌数

# 特殊处理10点牌（10, J, Q, K，总共16张每副牌）
num_cards[10] = decks * 4 * 4 - out_cards[10]  # 每副牌有16张10点牌
num_total += num_cards[10]                     # 加入剩余的10点牌数量

# 计算每张牌出现的概率
for i in range(1, 11):                         # 遍历点数1到10
    p[i] = num_cards[i] / num_total            # 概率 = 该点数剩余牌数量 / 总牌数

#print(f"num_cards[10]: {num_cards[10]}")       # 剩余的10点牌数量
#print(f"num_total: {num_total}")               # 总剩余牌数量
#print(f"p[10]: {p[10]}")                       # 剩余10点牌的概率

# ----------------------------------------------------------------------------------------------------------------------------#
# 第一步：定义 Soft_Bust 和 Hard_Bust （根据庄家的当前点数）
# ----------------------------------------------------------------------------------------------------------------------------#

# 初始化硬牌爆牌概率（17到21点为0，因为未爆牌；22点及以上为1，因为爆牌）
for i in range(17, 22):                                  # 17到21点
    Hard_Bust[i] = 0

for i in range(22, 32):                                  # 22到31点
    Hard_Bust[i] = 1

# 初始化软牌爆牌概率
for i in range(17, 22):                                  # 软牌17到21点
    Soft_Bust[i] = 0

for i in range(27, 32):                                  # 软牌27到31点（软牌最多可以27点未爆牌）
    Soft_Bust[i] = 0

# 计算硬牌爆牌概率（16到2点）
for i in range(16, 1, -1):                               # 从16点递减到2点
    for k in range(1, 11):                               # 遍历可能抽取的牌点数1到10
        if k == 1:                                       # 如果抽到A，则按软牌计算
            Hard_Bust[i] += p[k] * Soft_Bust[k + i + 10]
        else:                                            # 非A牌则按硬牌计算
            Hard_Bust[i] += p[k] * Hard_Bust[k + i]

    # 如果当前点数在12到16之间，初始化对应软牌爆牌概率
    if 11 < i < 17:                                      # 12到16点
        Soft_Bust[10 + i] = Hard_Bust[i]

    # 计算软牌爆牌概率（当i=6时，处理16到12点）
    if i == 6:
        for m in range(16, 11, -1):                      # 遍历软牌点数16到12
            for k in range(1, 11):                       # 遍历可能抽取的牌点数1到10
                Soft_Bust[m] += p[k] * Soft_Bust[k + m]  # 累加概率

# ----------------------------------------------------------------------------------------------------------------------------#
# 第二步：定义硬牌和软牌的概率矩阵（针对庄家的最终点数和当前点数）
# ----------------------------------------------------------------------------------------------------------------------------#

for i in range(17, 22):                      # 遍历庄家最终点数范围，从17到21
    for j in range(17, 22):                  # 遍历庄家当前点数范围，从17到21
        if i == j:                           # 如果最终点数与当前点数相等
            Hard_Hand[i, j] = 1              # 硬牌概率设置为1，表示不需要额外抽牌
            Soft_Hand[i, j] = 1              # 软牌概率同样设置为1
            
            # 检查软牌索引是否在矩阵范围内
            if j + 10 < Soft_Hand.shape[1]:  # 确保 j+10 索引在矩阵列数范围内
                Soft_Hand[i, j + 10] = 1     # 对应软牌（即将A视为11点的情况）的概率也设置为1

# ----------------------------------------------------------------------------------------------------------------------------#
# 第三步：定义庄家的最终点数为17、18、19、20、21的概率
# ----------------------------------------------------------------------------------------------------------------------------#

for n in range(17, 22):                                             # 遍历庄家最终点数17到21
    for i in range(16, 1, -1):                                      # 从庄家当前点数16递减到2
        for k in range(1, 11):                                      # 遍历可能抽取的牌点数1到10
            if k == 1:                                              # 如果抽到A
                Hard_Hand[n, i] += p[k] * Soft_Hand[n, k + i + 10]  # 按软牌概率计算
            else:  # 非A牌
                Hard_Hand[n, i] += p[k] * Hard_Hand[n, k + i]       # 按硬牌概率计算

        # 如果当前点数在12到16之间，则更新软牌概率
        if 11 < i < 17:
            Soft_Hand[n, 10 + i] = Hard_Hand[n, i]

        # 特殊处理当当前点数为6时
        if i == 6:
            for m in range(16, 11, -1):                             # 遍历点数16到12
                for k in range(1, 11):                              # 遍历可能抽取的牌点数1到10
                    Soft_Hand[n, m] += p[k] * Soft_Hand[n, k + m]   # 累加软牌概率

# ----------------------------------------------------------------------------------------------------------------------------#
# 第四步：庄家明牌点数计算（最终点数和第一张明牌点数）
# ----------------------------------------------------------------------------------------------------------------------------#

# 计算庄家爆牌概率
for i in range(1, 11):                                                # 遍历庄家第一张明牌的点数1到10
    if i > 1:                                                         # 如果第一张明牌不是A
        Dealer_Bust[i] = Hard_Bust[i]                                 # 直接等于硬牌爆牌概率
    else:                                                             # 如果第一张明牌是A
        for k in range(1, 11):                                        # 遍历可能抽取的牌点数1到10
            Dealer_Bust[i] += p[k] * Soft_Bust[k + i + 10]            # 累加软牌爆牌概率

    # 计算庄家最终点数为17到21的概率
    for k in range(17, 22):                                           # 遍历庄家最终点数17到21
        if i > 1:                                                     # 如果第一张明牌不是A
            Dealer_Hand[k, i] = Hard_Hand[k, i]                       # 直接等于硬牌概率
        else:                                                         # 如果第一张明牌是A
            for m in range(1, 11):                                    # 遍历可能抽取的牌点数1到10
                Dealer_Hand[k, i] += p[m] * Soft_Hand[k, m + i + 10]  # 累加软牌概率

# ----------------------------------------------------------------------------------------------------------------------------#

# 调整庄家Blackjack规则（即Blackjack Peek Rule）
Dealer_Hand[21, 1] -= p[10]          # 如果庄家明牌是A，扣除10点牌可能导致的Blackjack概率
Dealer_Hand[21, 10] -= p[1]          # 如果庄家明牌是10，扣除A可能导致的Blackjack概率

# 记录庄家拿到Blackjack的概率
Dealer_Hand_BJ[1] = p[10]            # 当庄家明牌是A时，拿到Blackjack的概率（即隐藏牌是10点牌）
Dealer_Hand_BJ[10] = p[1]            # 当庄家明牌是10时，拿到Blackjack的概率（即隐藏牌是A）

# 对概率进行归一化处理
Temp_Total = (                       # 临时变量，用于存储归一化前的概率总和
    Dealer_Hand[17, 1]               # 庄家明牌为A，最终点数为17的概率
    + Dealer_Hand[18, 1]             # 庄家明牌为A，最终点数为18的概率
    + Dealer_Hand[19, 1]             # 庄家明牌为A，最终点数为19的概率
    + Dealer_Hand[20, 1]             # 庄家明牌为A，最终点数为20的概率
    + Dealer_Hand[21, 1]             # 庄家明牌为A，最终点数为21的概率
    + Dealer_Bust[1]                 # 庄家明牌为A时爆牌的概率
)

# 归一化爆牌概率
Dealer_Bust[1] /= Temp_Total         # 将庄家明牌为A时的爆牌概率按总概率归一化

# ----------------------------------------------------------------------------------------------------------------------------#

# 归一化最终点数概率
for k in range(17, 22):                           # 遍历庄家最终点数范围（17到21）
    Dealer_Hand[k, 1] /= Temp_Total               # 将庄家明牌为A时每个点数的概率按总概率归一化

# 阶段1：站立策略 - 计算硬牌和软牌的站立概率
for k in range(4, 17):                            # 玩家手牌点数从4到16
    for i in range(1, 11):                        # 庄家明牌点数从1到10
        if i == 1:                                # 如果庄家明牌是A
            P_Hard_S[k, i] = (
                Dealer_Bust[i]                    # 庄家爆牌概率
                - Dealer_Hand[17, i]              # 减去庄家点数为17的概率
                - Dealer_Hand[18, i]              # 减去庄家点数为18的概率
                - Dealer_Hand[19, i]              # 减去庄家点数为19的概率
                - Dealer_Hand[20, i]              # 减去庄家点数为20的概率
                - Dealer_Hand[21, i]              # 减去庄家点数为21的概率
            )
        elif i == 10:                             # 如果庄家明牌是10点牌（包括10, J, Q, K）
            P_Hard_S[k, i] = (
                Dealer_Bust[i]                    # 庄家爆牌概率
                - Dealer_Hand[17, i]              # 减去庄家点数为17的概率
                - Dealer_Hand[18, i]              # 减去庄家点数为18的概率
                - Dealer_Hand[19, i]              # 减去庄家点数为19的概率
                - Dealer_Hand[20, i]              # 减去庄家点数为20的概率
                - Dealer_Hand[21, i]              # 减去庄家点数为21的概率
                - Dealer_Hand_BJ[10]              # 减去庄家拿到Blackjack的概率
            )
        else:                                     # 如果庄家明牌是其他点数（2到9）
            P_Hard_S[k, i] = (
                Dealer_Bust[i]                    # 庄家爆牌概率
                - Dealer_Hand[17, i]              # 减去庄家点数为17的概率
                - Dealer_Hand[18, i]              # 减去庄家点数为18的概率
                - Dealer_Hand[19, i]              # 减去庄家点数为19的概率
                - Dealer_Hand[20, i]              # 减去庄家点数为20的概率
                - Dealer_Hand[21, i]              # 减去庄家点数为21的概率
            )

        # 对于软牌点数（k > 11），将硬牌的站立概率复制到软牌
        if k > 11:                                # 当玩家手牌为软牌
            P_Soft_S[k, i] = P_Hard_S[k, i]       # 软牌与硬牌的站立概率相同
            P_Soft_S[k + 10, i] = P_Hard_S[k, i]  # 处理点数偏移的软牌站立概率

# ----------------------------------------------------------------------------------------------------------------------------#

# 额外计算 P_Hard_S 的值，针对玩家点数 17 到 21 的情况
for i in range(1, 11):  # 遍历庄家明牌点数（1到10）
    if i == 1:          # 当庄家明牌为 A
        # 分别计算玩家点数 17 到 21 的站立概率
        P_Hard_S[17, i] = (
            Dealer_Bust[i]
            - 0 * Dealer_Hand[17, i]
            - Dealer_Hand[18, i]
            - Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[18, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            - 0 * Dealer_Hand[18, i]
            - Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[19, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            - 0 * Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[20, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            + Dealer_Hand[19, i]
            - 0 * Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[21, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            + Dealer_Hand[19, i]
            + Dealer_Hand[20, i]
            - 0 * Dealer_Hand[21, i]
        )
    elif i == 10:       # 当庄家明牌为 10
        # 类似计算玩家点数 17 到 21 的站立概率，同时扣除庄家 Blackjack 概率
        P_Hard_S[17, i] = (
            Dealer_Bust[i]
            - 0 * Dealer_Hand[17, i]
            - Dealer_Hand[18, i]
            - Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
            - Dealer_Hand_BJ[10]
        )
        P_Hard_S[18, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            - 0 * Dealer_Hand[18, i]
            - Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
            - Dealer_Hand_BJ[10]
        )
        P_Hard_S[19, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            - 0 * Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
            - Dealer_Hand_BJ[10]
        )
        P_Hard_S[20, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            + Dealer_Hand[19, i]
            - 0 * Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
            - Dealer_Hand_BJ[10]
        )
        P_Hard_S[21, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            + Dealer_Hand[19, i]
            + Dealer_Hand[20, i]
            - 0 * Dealer_Hand[21, i]
            - Dealer_Hand_BJ[10]
        )
    else:              # 当庄家明牌为 2 到 9
        # 计算玩家点数 17 到 21 的站立概率（不涉及庄家 Blackjack）
        P_Hard_S[17, i] = (
            Dealer_Bust[i]
            - 0 * Dealer_Hand[17, i]
            - Dealer_Hand[18, i]
            - Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[18, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            - 0 * Dealer_Hand[18, i]
            - Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[19, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            - 0 * Dealer_Hand[19, i]
            - Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[20, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            + Dealer_Hand[19, i]
            - 0 * Dealer_Hand[20, i]
            - Dealer_Hand[21, i]
        )
        P_Hard_S[21, i] = (
            Dealer_Bust[i]
            + Dealer_Hand[17, i]
            + Dealer_Hand[18, i]
            + Dealer_Hand[19, i]
            + Dealer_Hand[20, i]
            - 0 * Dealer_Hand[21, i]
        )

# ----------------------------------------------------------------------------------------------------------------------------#

# 将 P_Hard_S 的值设置为 -1，针对玩家点数 22 到 31 的情况
for k in range(22, 32):                           # 遍历玩家点数从 22 到 31
    for i in range(1, 11):                        # 遍历庄家明牌点数从 1 到 10
        P_Hard_S[k, i] = -1                       # 超过21点为爆牌，设置为 -1 表示无效

# 计算软牌站立概率 P_Soft_S（玩家手牌和庄家明牌的概率）
for k in range(12, 32):                           # 遍历玩家点数从 12 到 31
    for i in range(1, 11):                        # 遍历庄家明牌点数从 1 到 10
        if k < 22:                                # 如果玩家点数小于 22（未爆牌）
            P_Soft_S[k, i] = P_Hard_S[k, i]       # 软牌站立概率与硬牌相同
        else:                                     # 如果玩家点数大于或等于 22（爆牌）
            P_Soft_S[k, i] = P_Hard_S[k - 10, i]  # 考虑软牌偏移10点后的硬牌概率

# ----------------------------------------------------------------------------------------------------------------------------#

# 阶段2：要牌和站立（Hit and Stand）
# 硬牌情况：玩家点数为 21 到 31
for k in range(21, 32):                                   # 遍历玩家点数从 21 到 31
    for i in range(1, 11):                                # 遍历庄家明牌点数从 1 到 10
        P_Hard_H[k, i] = -1                               # 玩家硬牌点数为 21 到 31 的要牌概率设置为 -1（无效）
        P_Soft_H[31, i] = -1                              # 玩家软牌点数为 31 的要牌概率也设置为 -1（无效）
        
        # 计算硬牌的站立和要牌综合概率
        P_Hard_HS[21, i] = max(P_Hard_S[21, i], P_Hard_H[21, i])
        
        # 计算软牌的站立和要牌综合概率
        P_Soft_HS[31, i] = max(P_Soft_S[31, i], P_Soft_H[31, i])

        if k > 21:                                        # 玩家硬牌点数超过 21 为爆牌
            P_Hard_HS[k, i] = -1                          # 综合概率设置为 -1（无效）

# 硬牌情况：玩家点数为 12 到 20
for m in range(20, 11, -1):                               # 从 20 点递减到 12 点
    for i in range(1, 11):                                # 遍历庄家明牌点数从 1 到 10
        for k in range(1, 11):                            # 遍历可能抽到的牌点数从 1 到 10
            if k == 1:                                    # 如果抽到 A
                P_Hard_H[m, i] += p[k] * P_Soft_HS[m + k + 10, i]
            else:                                         # 如果抽到非 A
                P_Hard_H[m, i] += p[k] * P_Hard_HS[m + k, i]

            # 软牌的要牌概率等于硬牌的要牌概率（偏移 10 点）
            P_Soft_H[m + 10, i] = P_Hard_H[m, i]

        # 计算硬牌的站立和要牌综合概率
        P_Hard_HS[m, i] = max(P_Hard_S[m, i], P_Hard_H[m, i])

        # 计算软牌的站立和要牌综合概率
        P_Soft_HS[m + 10, i] = max(P_Soft_S[m + 10, i], P_Soft_H[m + 10, i])

# 软牌情况：玩家点数为 12 到 21
for m in range(21, 11, -1):                               # 从 21 点递减到 12 点
    for i in range(1, 11):                                # 遍历庄家明牌点数从 1 到 10
        for k in range(1, 11):                            # 遍历可能抽到的牌点数从 1 到 10
            P_Soft_H[m, i] += p[k] * P_Soft_HS[m + k, i]  # 软牌要牌概率

        # 计算软牌的站立和要牌综合概率
        P_Soft_HS[m, i] = max(P_Soft_S[m, i], P_Soft_H[m, i])

# 硬牌情况：玩家点数为 4 到 11
for m in range(11, 3, -1):                                # 从 11 点递减到 4 点
    for i in range(1, 11):                                # 遍历庄家明牌点数从 1 到 10
        for k in range(1, 11):                            # 遍历可能抽到的牌点数从 1 到 10
            if k == 1:                                    # 如果抽到 A
                P_Hard_H[m, i] += p[k] * P_Soft_HS[m + k + 10, i]
            else:                                         # 如果抽到非 A
                P_Hard_H[m, i] += p[k] * P_Hard_HS[m + k, i]

        # 计算硬牌的站立和要牌综合概率
        P_Hard_HS[m, i] = max(P_Hard_S[m, i], P_Hard_H[m, i])

# 阶段2：要牌和站立完成

# ----------------------------------------------------------------------------------------------------------------------------#

# 阶段3：要牌、站立和加倍（Hit, Stand, Double）
# 硬牌情况：玩家点数为 21 到 31
for k in range(21, 32):            # 遍历玩家点数从 21 到 31
    for i in range(1, 11):         # 遍历庄家明牌点数从 1 到 10
        # 计算硬牌的站立、要牌和加倍综合概率
        P_Hard_HSD[21, i] = max(P_Hard_S[21, i], P_Hard_H[21, i], P_Hard_D[21, i])
        
        # 计算软牌的站立、要牌和加倍综合概率
        P_Soft_HSD[31, i] = max(P_Soft_S[31, i], P_Soft_H[31, i], P_Soft_D[31, i])

        if k > 21:                 # 如果玩家点数超过 21（爆牌）
            P_Hard_HSD[k, i] = -1  # 综合概率设置为无效

# 硬牌情况：玩家点数为 12 到 20
for m in range(20, 11, -1):        # 从玩家点数 20 递减到 12
    for i in range(1, 11):         # 遍历庄家明牌点数从 1 到 10
        for k in range(1, 11):     # 遍历可能抽到的牌点数从 1 到 10
            if k == 1:             # 如果抽到 A
                P_Hard_D[m, i] += 2 * p[k] * P_Soft_S[m + k + 10, i]
            else:                  # 如果抽到非 A
                P_Hard_D[m, i] += 2 * p[k] * P_Hard_S[m + k, i]

            # 软牌加倍的概率与硬牌相同（偏移 10 点）
            P_Soft_D[m + 10, i] = P_Hard_D[m, i]

        # 计算硬牌的站立、要牌和加倍综合概率
        P_Hard_HSD[m, i] = max(P_Hard_S[m, i], P_Hard_H[m, i], P_Hard_D[m, i])

        # 计算软牌的站立、要牌和加倍综合概率
        P_Soft_HSD[m + 10, i] = max(P_Soft_S[m + 10, i], P_Soft_H[m + 10, i], P_Soft_D[m + 10, i])

# 软牌情况：玩家点数为 12 到 21
for m in range(21, 11, -1):        # 从玩家点数 21 递减到 12
    for i in range(1, 11):         # 遍历庄家明牌点数从 1 到 10
        for k in range(1, 11):     # 遍历可能抽到的牌点数从 1 到 10
            # 计算软牌加倍的概率
            P_Soft_D[m, i] += 2 * p[k] * P_Soft_S[m + k, i]

        # 计算软牌的站立、要牌和加倍综合概率
        P_Soft_HSD[m, i] = max(P_Soft_S[m, i], P_Soft_H[m, i], P_Soft_D[m, i])

# 硬牌情况：玩家点数为 4 到 11
for m in range(11, 3, -1):         # 从玩家点数 11 递减到 4
    for i in range(1, 11):         # 遍历庄家明牌点数从 1 到 10
        for k in range(1, 11):     # 遍历可能抽到的牌点数从 1 到 10
            if k == 1:             # 如果抽到 A
                P_Hard_D[m, i] += 2 * p[k] * P_Soft_S[m + k + 10, i]
            else:                  # 如果抽到非 A
                P_Hard_D[m, i] += 2 * p[k] * P_Hard_S[m + k, i]

        # 计算硬牌的站立、要牌和加倍综合概率
        P_Hard_HSD[m, i] = max(P_Hard_S[m, i], P_Hard_H[m, i], P_Hard_D[m, i])

# 阶段3：要牌、站立和加倍完成

# ----------------------------------------------------------------------------------------------------------------------------#

# 阶段4：分牌策略（Split）

for m in range(10, 0, -1):          # 从 10 点递减到 1 点
    if m == 1:                      # 特殊情况：玩家手牌为两张 A
        for i in range(1, 11):      # 遍历庄家明牌点数从 1 到 10
            for k in range(1, 11):  # 遍历可能抽到的牌点数从 1 到 10
                # 计算分牌后两副牌的概率
                P_Split[m, i] += 2 * p[k] * P_Soft_S[m + k + 10, i]
                
            # 计算是否选择分牌的综合概率
            P_Split_YN[m, i] = max(P_Split[m, i], P_Soft_HS[2 * m + 10, i])
    else:                           # 通常情况：玩家手牌为两张其他点数
        for i in range(1, 11):      # 遍历庄家明牌点数从 1 到 10
            for k in range(1, 11):  # 遍历可能抽到的牌点数从 1 到 10
                if k == 1:          # 如果抽到 A
                    # 分牌后两副牌中包含软牌的概率
                    P_Split[m, i] += 2 * p[k] * P_Soft_HS[m + k + 10, i]
                else:               # 如果抽到非 A
                    # 分牌后两副牌中包含硬牌的概率
                    P_Split[m, i] += 2 * p[k] * P_Hard_HS[m + k, i]

            # 计算是否选择分牌的综合概率
            P_Split_YN[m, i] = max(P_Split[m, i], P_Hard_HS[2 * m, i])

# 阶段4：分牌策略完成

# ----------------------------------------------------------------------------------------------------------------------------#

# 初始化玩家手牌数组，大小为22，用于记录每种点数牌的数量
player_hands = np.zeros(22, dtype=int)

# 初始化玩家点数和总点数的变量
playerpoint = None                           # 玩家点数初始为 None
playerpoint = 0                              # 玩家点数设置为 0
dealer_up = int                              # 庄家明牌点数的变量
player_total = int                           # 玩家手牌总点数的变量
dealer_up = 0                                # 庄家明牌点数初始化为 0

# 模拟从实际游戏中输入玩家手牌和庄家明牌点数
# 庄家明牌点数为 7
dealer_up = 4

# 玩家第一张及接下来所获得的牌
player_hands[1] = 6                          
player_hands[2] = 8                          
player_hands[3] = 0                          
player_hands[4] = 0
player_hands[5] = 0
player_hands[6] = 0
player_hands[7] = 0
player_hands[8] = 0
player_hands[9] = 0
player_hands[10] = 0
player_hands[11] = 0
player_hands[12] = 0
player_hands[13] = 0
player_hands[14] = 0
player_hands[15] = 0
player_hands[16] = 0
player_hands[17] = 0
player_hands[18] = 0
player_hands[19] = 0
player_hands[20] = 0
player_hands[21] = 0

# 定义牌值映射
card_value_mapping = {
    "A": 1,  # Ace按1处理（如果需要按11处理，可以修改逻辑）
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}

# 打开文件并读取内容
with open("hands_vertical.txt", "r") as file:
    lines = file.readlines()

# 提取庄家和玩家的点数
dealer_raw = lines[0].strip()  # 第一行是庄家的明牌点数
if dealer_raw in card_value_mapping:
    dealer_up = card_value_mapping[dealer_raw]  # 转换为数值点数
else:
    raise ValueError(f"Invalid card value: {dealer_raw}")

player_cards_raw = [line.strip() for line in lines[1:]]  # 剩下的行是玩家的手牌
player_cards = []
for card in player_cards_raw:
    if card in card_value_mapping:
        player_cards.append(card_value_mapping[card])
    else:
        raise ValueError(f"Invalid card value: {card}")

# 初始化玩家手牌数组
player_hands = [0] * 22  # 玩家手牌，最大支持 21 张牌

# 将玩家手牌写入 player_hands
for i, card in enumerate(player_cards, start=1):
    player_hands[i] = card

player_total = 0                             # 玩家手牌总点数初始化为 0
# 遍历玩家手牌数组，计算玩家手牌总点数
for i in range(1, 22):                       # 遍历 1 到 21 的索引
    player_total += player_hands[i]          # 累加每种点数牌的数量到玩家总点数

# 定义输出文件路径
output_file = "Best_Strategy.txt"

# 打开文件写入模式
with open(output_file, "w") as file:
    # 检查玩家手牌中是否有A，且总点数小于11（软牌的情况）
    if 1 in player_hands and player_total < 11:
        # 如果庄家明牌为 A，计算保险值并输出
        if dealer_up == 1:  # 庄家明牌为 A
            #print(f"p[10]: {p[10]}")  # 打印 p[10] 的值
            insurance_ev = 3 * p[10] - 1  # 按公式计算
            #print(f"Calculated Insurance EV: {insurance_ev}")  # 打印计算结果
            output = f"{'Insurance EV':<13} = {round(insurance_ev, 4)}"  # 确保输出负值
            file.write(output + "\n")

        # 检查是否符合分牌条件：只有两张同点数的牌，且点数为1和2，同时没有其他牌
        if player_hands[1] == player_hands[2] and player_hands[3] < 1 and player_hands[1] > 0:
            # 输出分牌的概率
            output = f"{'Split':<13} = {round(P_Split[player_hands[1], dealer_up], 4)}"
            file.write(output + "\n")
        else:
            output = "\nAvailable Decision Probabilities\nNo Split"
            file.write(output + "\n")

        # 输出软牌的各种策略概率
        output = f"{'Soft Hit':<13} = {round(P_Soft_H[player_total + 10, dealer_up], 4)}"
        file.write(output + "\n")

        output = f"{'Soft Double':<13} = {round(P_Soft_D[player_total + 10, dealer_up], 4)}"
        file.write(output + "\n")

        output = f"{'Soft Stand':<13} = {round(P_Soft_S[player_total + 10, dealer_up], 4)}"
        file.write(output + "\n")

        # 判断最佳策略
        if P_Split_YN[player_hands[1], dealer_up] == P_Split[player_hands[2], dealer_up] == P_Split[player_hands[1], dealer_up] and player_hands[3] < 1:
            output = f"{'Best Strategy':<13} = Split"
        else:
            if P_Soft_HSD[player_total + 10, dealer_up] == P_Soft_H[player_total + 10, dealer_up]:
                output = f"{'Best Strategy':<13} = Hit"
            elif P_Soft_HSD[player_total + 10, dealer_up] == P_Soft_D[player_total + 10, dealer_up]:
                output = f"{'Best Strategy':<13} = Double"
            else:
                output = f"{'Best Strategy':<13} = Stand"
        file.write(output + "\n")

    # 如果玩家没有软牌或总点数大于等于11（硬牌的情况）
    else:
        # 如果庄家明牌为 A，计算保险值并输出
        if dealer_up == 1:  # 庄家明牌为 A
            #print(f"p[10]: {p[10]}")  # 打印 p[10] 的值
            insurance_ev = 3 * p[10] - 1  # 按公式计算
            #print(f"Calculated Insurance EV: {insurance_ev}")  # 打印计算结果
            output = f"{'Insurance EV':<13} = {round(insurance_ev, 4)}"  # 输出保险值
            file.write(output + "\n")

        # 检查是否符合分牌条件：只有两张同点数的牌，且没有其他牌
        if player_hands[1] == player_hands[2] and player_hands[3] < 1 and player_hands[1] > 0:
            output = f"{'Split':<13} = {round(P_Split[player_hands[1], dealer_up], 4)}"
            file.write(output + "\n")
        else:
            output = "\nAvailable Decision Probabilities\nNo Split"
            file.write(output + "\n")

        # 输出硬牌的各种策略概率
        output = f"{'Hard Hit':<13} = {round(P_Hard_H[player_total, dealer_up], 4)}"
        file.write(output + "\n")

        output = f"{'Hard Double':<13} = {round(P_Hard_D[player_total, dealer_up], 4)}"
        file.write(output + "\n")

        output = f"{'Hard Stand':<13} = {round(P_Hard_S[player_total, dealer_up], 4)}"
        file.write(output + "\n")

        # 判断最佳策略
        if P_Split_YN[player_hands[1], dealer_up] == P_Split[player_hands[2], dealer_up] == P_Split[player_hands[1], dealer_up] and player_hands[3] < 1:
            output = f"{'Best Strategy':<13} = Split"
        else:
            if P_Hard_HSD[player_total, dealer_up] == P_Hard_H[player_total, dealer_up]:
                output = f"{'Best Strategy':<13} = Hit"
            elif P_Hard_HSD[player_total, dealer_up] == P_Hard_D[player_total, dealer_up]:
                output = f"{'Best Strategy':<13} = Double"
            else:
                output = f"{'Best Strategy':<13} = Stand"
        file.write(output + "\n")




          