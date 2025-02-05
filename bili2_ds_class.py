import os
import re
import json
import time
import requests
import datetime
import random
#2025 2 6
#！！！有三个url不能保存

# =======================
# 配置类:获取用户输入,保存基本配置信息
# =======================
class Config:
    COOKIE = "_uuid=FAA377D6-ED9F-310BC-519A-42C2B9B91062F10710infoc; buvid_fp=075b92ba210dd98d64009eaf6c2cbc64; buvid3=11EF371E-DBF9-D8D2-2B7D-5D0CE0A3AF4A22211infoc; b_nut=1732329713; header_theme_version=CLOSE; enable_web_push=DISABLE; match_float_version=ENABLE; DedeUserID=6967383; DedeUserID__ckMd5=9eb8b539885d768e; rpdid=|(u)YJJl~Rk~0J'u~JkJJJ)u~; buvid4=828502D2-463E-0EEA-9493-3B1F42F715AD66991-022073012-37bAVZ3%2FgV8gtfbxn3o9vQ%3D%3D; home_feed_column=4; fingerprint=075b92ba210dd98d64009eaf6c2cbc64; hit-dyn-v2=1; share_source_origin=COPY; CURRENT_QUALITY=80; bsource=search_baidu; enable_feed_channel=DISABLE; LIVE_BUVID=AUTO2617385612857275; PVID=1; SESSDATA=4495dab3%2C1754205181%2C3c415%2A22CjDz1NT6NAmsQCf0_a-_6EQXUVzLnGhdnBuwi2wVNFnmMoKrooacWrI5vo7sfM5sSUgSVk9telRPQVpjZmt4R1lhY3c1ajQyOUQ3ZF9Ec0plS3hUbkZYZ05RWVh6Z01xUVM2RWNpVGR2bmxyTDJrdDdYbUFlN2ZUb3RuNDdyQ1lsVXFYSHpvSDdBIIEC; bili_jct=171d07c17cfb829035f21dbdbcc25866; sid=6r5x9fa6; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Mzg5MTk5ODksImlhdCI6MTczODY2MDcyOSwicGx0IjotMX0.VCrjyYzAgqo5t0doI8EIfreG2uXFRsF7MeYqtAqIRaU; bili_ticket_expires=1738919929; bp_t_offset_6967383=1030211527296155648; CURRENT_FNVAL=4048; browser_resolution=426-511; b_lsid=DD109777B_194D3AE6299"  # 全局 COOKIE

    def __init__(self, download_dir=None, uid=None, interval=None):
        self.download_dir = download_dir or self.get_download_dir()
        self.uid = uid or self.get_uid()
        self.interval = interval or self.get_interval()
        #在目录self.download_dir下创建saved_url.txt和unsaved_url.txt
        self.saved_url_filename = os.path.join(self.download_dir, "saved_url.txt")
        self.unsaved_url_filename = os.path.join(self.download_dir, "unsaved_url.txt")
        # 确保下载目录存在
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def get_download_dir(self):
        download_dir = input("请输入下载目录(默认为 C:\Base1\\bbb\\bili):").strip()
        return download_dir if download_dir else r"C:\Base1\bbb\bili"

    def get_uid(self):
        uid = input("请输入bilibili用户uid(默认为560647):").strip()
        return uid if uid else "560647"

    def get_interval(self):
        interval = input("请输入下载间隔(秒,默认为3):").strip()
        try:
            return float(interval) if interval else 3
        except Exception:
            return 3

# =======================
# 文件操作类:处理文件的读写、存在性检查等
# =======================
class FileManager:
    def __init__(self, config: Config):
        self.config = config
        self.ensure_file_exists(self.config.saved_url_filename)
        self.ensure_file_exists(self.config.unsaved_url_filename)

    def ensure_file_exists(self, filename):
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                pass

    def load_url_set(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return {line.strip() for line in f if line.strip()}
        else:
            return set()

    def write_url_file(self, filename, urls):
        """覆盖写入 URL 文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + "\n")

    def append_url_file(self, filename, urls):
        """追加写入 URL 文件"""
        with open(filename, 'a', encoding='utf-8') as f:
            for url in urls:
                f.write(url + "\n")

# =======================
# 工具类:提供公共工具方法
# =======================
class Utils:
    ILLEGAL_CHAR_PATTERN = r'[<>:"/\\|?*\n\r]'

    @staticmethod
    def sanitize_filename(name, max_length=50):
        name = re.sub(Utils.ILLEGAL_CHAR_PATTERN, '', name)
        if len(name) > max_length:
            name = name[:max_length]
        return name

    @staticmethod
    def parse_dynamic_card(card_str):
        try:
            card_dict = json.loads(card_str)
            return card_dict
        except Exception as e:
            print("解析 card 失败:", e)
            return {}

    @staticmethod
    def format_datetime(timestamp):
        dt = datetime.datetime.fromtimestamp(timestamp)
        # 月份、日期不带前导零
        return f"{dt.year}-{dt.month}-{dt.day}-{dt.hour:02d}:{dt.minute:02d}"

# =======================
# 下载类:负责文件下载(例如图片下载)
# =======================
class Downloader:
    def __init__(self, config: Config):
        self.config = config
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/90.0.4430.93 Safari/537.36"),
            "Cookie": config.COOKIE
        }

    def download_file(self, url, filepath):
        try:
            random_number = random.uniform(0.6, 0.8)
            time.sleep(random_number)#延迟
            r = requests.get(url, headers=self.headers, stream=True, timeout=10)
            if r.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                print(f"保存文件:{filepath}")
            else:
                print(f"下载失败 {url} 状态码:{r.status_code}")
        except Exception as e:
            print(f"下载 {url} 出错:{e}")

# =======================
# 动态处理类:处理单条动态,生成文件夹、info.txt,并下载图片
# =======================
class DynamicProcessor:
    def __init__(self, config: Config, file_manager: FileManager, downloader: Downloader):
        self.config = config
        self.file_manager = file_manager
        self.downloader = downloader

    def process_dynamic(self, dynamic, saved_url_set, success_list, failed_list):
        dynamic_url = None
        try:
            random_number = random.uniform(0.2, 0.4)
            time.sleep(random_number)
            desc = dynamic.get("desc", {})
            dynamic_id = desc.get("dynamic_id")
            if not dynamic_id:
                print("无法获取 dynamic_id,跳过该动态")
                return
            dynamic_id = str(dynamic_id)  # 确保 dynamic_id 是字符串
            dynamic_url = f"https://t.bilibili.com/{dynamic_id}"
            if dynamic_url in saved_url_set:
                print(f"动态 {dynamic_url} 已下载,跳过。")
                return

            # 发布时间
            timestamp = desc.get("timestamp")
            time_str = Utils.format_datetime(timestamp) if timestamp else "未知时间"

            # 解析动态详情
            card_str = dynamic.get("card", "")
            card_dict = Utils.parse_dynamic_card(card_str)

            # 获取动态内容:优先取 description,再取 content
            dynamic_content = ""
            if "item" in card_dict:
                item = card_dict["item"]
                if "description" in item:
                    dynamic_content = item["description"]
                elif "content" in item:
                    dynamic_content = item["content"]

            # 判断动态是否有内容(去除空白字符后是否为空)
            has_content = bool(dynamic_content.strip())
            if has_content:
                content_clean = Utils.sanitize_filename(dynamic_content, max_length=50)
                folder_name = f"{time_str}-{content_clean}"
                folder_name = Utils.sanitize_filename(folder_name)
                dynamic_folder = os.path.join(self.config.download_dir, folder_name)
            else:
                # 如果动态内容为空,则放在 download_dir/null 下,以 dynamic_id 命名子文件夹
                null_folder = os.path.join(self.config.download_dir, "null")
                if not os.path.exists(null_folder):
                    os.makedirs(null_folder)
                    print(f"创建空内容动态存放文件夹: {null_folder}")
                dynamic_folder = os.path.join(null_folder, dynamic_id)

            if not os.path.exists(dynamic_folder):
                os.makedirs(dynamic_folder)
                print(f"创建文件夹: {dynamic_folder}")
            else:
                print(f"文件夹已存在: {dynamic_folder}")

            # 生成 info.txt,包含 URL、发布时间和完整内容
            info_path = os.path.join(dynamic_folder, "info.txt")
            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {dynamic_url}\n")
                f.write(f"发布时间: {time_str}\n")
                f.write("内容:\n")
                f.write(dynamic_content)
            print(f"保存动态信息到: {info_path}")

            # 下载图片(如果有)
            pics = []
            if "item" in card_dict and "pictures" in card_dict["item"]:
                pics = card_dict["item"]["pictures"]
            if pics:
                for idx, pic in enumerate(pics, start=1):
                    img_url = pic.get("img_src")
                    if not img_url:
                        continue
                    ext = os.path.splitext(img_url)[1]
                    if not ext:
                        ext = ".jpg"
                    img_filename = f"{idx}{ext}"
                    img_path = os.path.join(dynamic_folder, img_filename)
                    print(f"下载图片: {img_url}")
                    self.downloader.download_file(img_url, img_path)
            else:
                print("该动态没有图片。")

            # 记录处理成功
            saved_url_set.add(dynamic_url)
            success_list.append(dynamic_url)
        except Exception as e:
            print("处理动态出错:", e)
            if dynamic_url:
                failed_list.append(dynamic_url)

# =======================
# 主爬虫类:分页获取动态数据,并调用 DynamicProcessor 处理每条动态
# =======================
class BilibiliDynamicSpider:
    def __init__(self, config: Config, file_manager: FileManager, dynamic_processor: DynamicProcessor):
        self.config = config
        self.file_manager = file_manager
        self.dynamic_processor = dynamic_processor
        self.saved_url_set = self.file_manager.load_url_set(self.config.saved_url_filename)
        self.success_list = []
        self.failed_list = []

    def run(self):
        base_url = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
        params = {"host_uid": self.config.uid, "offset_dynamic_id": 0}
        has_more = True
        page_count = 1

        while has_more:
            print(f"正在处理第 {page_count} 页动态...")
            try:
                response = requests.get(base_url, headers=self.dynamic_processor.downloader.headers, params=params, timeout=10)
                if response.status_code != 200:
                    print("请求失败,状态码:", response.status_code)
                    break
                data = response.json()
                if data.get("code") != 0:
                    print("接口返回错误信息:", data.get("message"))
                    break

                data_data = data.get("data", {})
                cards = data_data.get("cards", [])
                has_more = data_data.get("has_more", False)
                if "next_offset" in data_data:
                    params["offset_dynamic_id"] = data_data["next_offset"]
                else:
                    if cards:
                        last_card = cards[-1]
                        last_desc = last_card.get("desc", {})
                        params["offset_dynamic_id"] = last_desc.get("dynamic_id", 0)
                    else:
                        has_more = False

                if not cards:
                    print("当前页没有动态数据,结束下载。")
                    break

                for dynamic in cards:
                    self.dynamic_processor.process_dynamic(dynamic, self.saved_url_set, self.success_list, self.failed_list)

                page_count += 1
                print(f"等待 {self.config.interval} 秒后继续下载下一页...")
                time.sleep(self.config.interval)
            except Exception as e:
                print("处理页面时发生错误:", e)
                break

        # 将本次成功的 URL 追加写入 saved_url.txt
        if self.success_list:
            self.file_manager.append_url_file(self.config.saved_url_filename, self.success_list)
        # 将本次失败的 URL 覆盖写入 unsaved_url.txt
        self.file_manager.write_url_file(self.config.unsaved_url_filename, self.failed_list)

        print("下载完成！")
        print(f"成功处理 {len(self.success_list)} 条动态,失败 {len(self.failed_list)} 条。")

# =======================
# 主函数
# =======================
def main():
    # 初始化各个模块
    config = Config()  # 若需要可传入参数,否则将通过 input 获取
    file_manager = FileManager(config)
    downloader = Downloader(config)
    dynamic_processor = DynamicProcessor(config, file_manager, downloader)
    spider = BilibiliDynamicSpider(config, file_manager, dynamic_processor)
    # 启动爬虫
    
    spider.run()

if __name__ == "__main__":
    main()