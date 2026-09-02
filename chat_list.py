import json
import random
import string

chat_list = [ "gnRszLKDHSBA",
        "ysczWmowGgHaIcUsZK",
        "ofVR5U0EjjsAzG21",
        "nnUyieSK5nDm5tNa",
        "BR2zzTZG8S8lF3TJMsnH68S",
        "Af0uGX22nxNpo5CH9VH4hvC",
        "PpthOV5waF8O",
        "CLAB2Vt4LOpXGA",
        "26nKB9Ho4tqDTlOACM4LvltJl",
        "PcLNBP0bLigNW1V1Iy",
        "bv18",
        "wl5o3k9K2U",
        "VRkuFZPSXfkLT0N0weet",
        "cMr",
        "o9EZTM1u3iIF34XyGcye7gk",
        "VV2D",
        "ajTLW003XS",
        "10Id1",
        "gf96wvtKhSu1jPiv02sjT6d",
        "na89EZ6AOf2bH3kdOtPAWD",
        "秋张黄翔唐罪宇字虞人衣海有官",
        "朝天",
        "龙殷往有字淡朝辰往",
        "列藏坐来日收",
        "宿殷帝来暑唐人荒",
        "垂官来乃翔道人唐鳞人张收淡翔",
        "制虞宙章皇宙暑乃鸟有羽淡翔玄",
        "海垂天问昃宙坐衣",
        "问文往天周月衣海鸟",
        "火宿秋始唐字天火乃衣师乃",
        "昃冬海",
        "冬乃盈寒淡秋日鸟",
        "制羽朝罪来师秋拱张秋始周虞让宿",
        "道月乃人羽道淡火寒问乃陶始",
        "羽潜帝",
        "翔拱文唐伐",
        "制乃发日民服张宙国衣",
        "让民",
        "潜淡宙人汤帝坐天服虞汤推鸟咸皇",
        "寒朝日人鳞让服淡辰"]

print(random.choice(chat_list))

# # 常用中文汉字库（用于随机组合生成不同长度的中文字符串）
# CHINESE_CHARS = (
#     "天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏"
#     "海咸河淡鳞潜羽翔龙师火帝鸟官人皇始制文字乃服衣裳"
#     "推位让国有虞陶唐吊民伐罪周发殷汤坐朝问道垂拱平章"
# )

# # 生成 20 个不同长度的英文字符串 (长度随机范围 3 到 25)
# english_list = [
#     "".join(
#         random.choices(
#             string.ascii_letters + string.digits, k=random.randint(3, 25)
#         )
#     )
#     for _ in range(20)
# ]

# # 生成 20 个不同长度的中文字符串 (长度随机范围 2 到 15)
# chinese_list = [
#     "".join(random.choices(CHINESE_CHARS, k=random.randint(2, 15)))
#     for _ in range(20)
# ]

# # 组合数据结构
# data = {"english_list": english_list, "chinese_list": chinese_list}

# # 输出为 JSON 字符串 (ensure_ascii=False 确保中文字符不被转义)
# json_output = json.dumps(data, ensure_ascii=False, indent=2)

# # 打印结果
# print(json_output)

# # 保存到本地文件
# with open("output.json", "w", encoding="utf-8") as f:
#     f.write(json_output)