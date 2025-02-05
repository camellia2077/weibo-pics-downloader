#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlsplit

# 全局 COOKIE 变量
COOKIE = "_uui"

# 设置请求头，模拟真实浏览器，同时带上 COOKIE
headers = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/90.0.4430.93 Safari/537.36"),
    "Cookie": COOKIE
}


def sanitize_filename(name):
    """
    去除 Windows 文件夹/文件名中的非法字符
    """
    return re.sub(r'[\\/:*?"<>|]', '', name)


def process_post(post_url, title, content, pubtime, base_dir):
    """
    下载单个帖子的页面，解析评论区图片，并保存帖子详情和图片
    """
    # 请求帖子详情页面
    resp = requests.get(post_url, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise Exception("获取帖子页面失败，状态码：" + str(resp.status_code))
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # 生成文件夹名称：
    # 先取标题，没有标题则取正文，没有正文则用“无正文”
    base_name = title if title.strip() else (content if content.strip() else "无正文")
    folder_name = f"{pubtime} {base_name}"
    folder_name = sanitize_filename(folder_name)
    if len(folder_name) > 30:
        folder_name = folder_name[:30]
    folder_path = os.path.join(base_dir, folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print("创建文件夹:", folder_path)
    else:
        print("文件夹已存在:", folder_path)

    # 保存帖子信息到 content.txt
    content_file = os.path.join(folder_path, "content.txt")
    with open(content_file, "w", encoding="utf-8") as f:
        f.write(f"URL: {post_url}\n")
        f.write(f"标题: {title}\n")
        f.write(f"正文: {content}\n")
        f.write(f"发布时间: {pubtime}\n")
    print("保存帖子内容到", content_file)

    # 从页面中查找评论区图片
    # 示例中假定评论区所在的 div 的 id 为 "comment" 或 class 为 "comment-area"
    comment_div = soup.find("div", id="comment")
    if not comment_div:
        comment_div = soup.find("div", class_="comment-area")
    if comment_div:
        imgs = comment_div.find_all("img")
    else:
        imgs = []
    print(f"检测到 {len(imgs)} 张评论区图片")

    # 依次下载图片，并保存为 1.ext, 2.ext, … 等
    for idx, img in enumerate(imgs, start=1):
        img_url = img.get("src")
        if not img_url:
            continue
        # 如果图片地址不完整，可根据需要补全（例如加上 https: 前缀）
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        # 获取图片后缀，若无法解析则默认为 .jpg
        path = urlsplit(img_url).path
        _, ext = os.path.splitext(path)
        if not ext:
            ext = ".jpg"
        img_filename = f"{idx}{ext}"
        img_path = os.path.join(folder_path, img_filename)
        try:
            img_resp = requests.get(img_url, headers=headers, stream=True, timeout=10)
            if img_resp.status_code == 200:
                with open(img_path, "wb") as f:
                    for chunk in img_resp.iter_content(1024):
                        f.write(chunk)
                print(f"保存图片 {img_filename}")
            else:
                print(f"下载图片失败 {img_url} 状态码: {img_resp.status_code}")
        except Exception as e:
            print(f"下载图片 {img_url} 出错: {e}")


def main():
    # 通过 input 获取自定义下载目录，uid，和下载间隔
    download_dir = input("请输入下载目录(默认 C:\\Base1\\bbb\\bili): ").strip()
    if not download_dir:
        download_dir = r"C:\Base1\bbb\bili"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    uid = input("请输入用户 uid(默认 560647): ").strip()
    if not uid:
        uid = "560647"

    interval_input = input("请输入下载间隔秒数(默认 3): ").strip()
    try:
        interval = float(interval_input) if interval_input else 3
    except:
        interval = 3

    # 在指定目录下创建保存已下载和未下载成功帖子 URL 的文件
    saved_file = os.path.join(download_dir, "saved_url.txt")
    unsaved_file = os.path.join(download_dir, "unsaved_url.txt")
    if not os.path.exists(saved_file):
        with open(saved_file, "w", encoding="utf-8") as f:
            pass
    if not os.path.exists(unsaved_file):
        with open(unsaved_file, "w", encoding="utf-8") as f:
            pass

    # 加载已保存的 URL 到集合中，便于防重复爬取
    with open(saved_file, "r", encoding="utf-8") as f:
        saved_urls = set(line.strip() for line in f if line.strip())

    page = 1
    while True:
        print(f"\n正在获取第 {page} 页数据……")
        # 示例中使用 bilibili 文章接口（实际接口可能不同）
        api_url = f"https://api.bilibili.com/x/space/article?mid={uid}&pn={page}"
        try:
            resp = requests.get(api_url, headers=headers, timeout=10)
            # 假定返回 json 格式数据
            data = resp.json()
        except Exception as e:
            print("获取数据失败:", e)
            break

        # 根据返回数据结构提取文章列表
        # 示例中假定 data["data"]["articles"] 为帖子列表
        articles = data.get("data", {}).get("articles", [])
        if not articles:
            print("没有更多数据，退出爬取。")
            break

        # 逐条处理帖子
        for article in articles:
            # 假定每条数据包含以下字段：
            #   - "arcurl" 帖子 URL
            #   - "title" 帖子标题
            #   - "summary" 帖子正文/摘要（如果正文较长，可能需要进一步请求详情页）
            #   - "pubdate" 发布时间（unix 时间戳）
            post_url = article.get("arcurl")
            title = article.get("title", "")
            content = article.get("summary", "")
            pubdate = article.get("pubdate")
            pubtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(pubdate)) if pubdate else "未知时间"

            if not post_url:
                continue

            # 防重复：如果 URL 已在 saved_file 中，则跳过
            if post_url in saved_urls:
                print("跳过已下载的帖子:", post_url)
                continue

            print("\n开始下载帖子:", post_url)
            try:
                process_post(post_url, title, content, pubtime, download_dir)
                # 下载成功后，将 URL 追加到 saved_url.txt
                with open(saved_file, "a", encoding="utf-8") as f:
                    f.write(post_url + "\n")
                saved_urls.add(post_url)
            except Exception as e:
                print("下载帖子出错:", e)
                with open(unsaved_file, "a", encoding="utf-8") as f:
                    f.write(post_url + " 错误: " + str(e) + "\n")
            # 下载完一条帖子后等待设定间隔
            time.sleep(interval)

        page += 1


if __name__ == '__main__':
    main()
