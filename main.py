# -*- coding: utf-8 -*-
# @Date    : 2016/9/9
# @Author  : hrwhisper
import codecs
import json
import re
import os
import io
import subprocess
import multiprocessing
from multiprocessing.dummy import Pool
from datetime import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup
from LoginUCAS import LoginUCAS

class UCASVideo(object):
    def __init__(self):
        self.name = '' #网站上该视频的名称
        # self.play_page_url = '' #课程视频的播放链接
        self.u3m8_url = '' #加密地址
        self.dir_name = ''

    def __init__(self, name:'str', u3m8_url:'str', dirname = ''):

        self.name = name #网站上该视频的名称
        # self.play_page_url = play_page_url #课程视频的播放链接
        self.u3m8_url = u3m8_url #加密地址
        self.dir_name = dirname

class UCASCourse(object):
    def __init__(self):
        # self.work_space = 'http://sep.ucas.ac.cn/portal/site/16/801'
        self.name = ''
        self.url_base = '' # 如 https://course.ucas.ac.cn/portal/site/174896
        self.resource_page_url = '' #
        self.video_page_conmon_url = ''

        self.course_video_page_url = ''
        self.live_video_page_url = ''

        self.course_video_list =[] #保存UCASVideo列表
        self.live_video_list = []

        #视频多页的情况
        self.course_video_current_page = 1
        self.live_video_current_page = 1

    def __init__(self, name, url_base):
        # self.work_space = 'http://sep.ucas.ac.cn/portal/site/16/801'
        self.name = name
        self.url_base = url_base # 如 https://course.ucas.ac.cn/portal/site/174896
        self.resource_page_url = '' #
        self.video_page_conmon_url = ''

        self.course_video_page_url = ''
        self.live_video_page_url = ''

        self.course_video_list =[] #保存UCASVideo列表
        self.live_video_list = []

        #视频多页的情况
        self.course_video_current_page = 1
        self.live_video_current_page = 1

        # def __init__(self, course:'UCASCourse'):
        #     # self.work_space = 'http://sep.ucas.ac.cn/portal/site/16/801'
        #     self.name = course.name
        #     self.url_base = course.url_base  # 如 https://course.ucas.ac.cn/portal/site/174896
        #     self.resource_page_url = course.resource_page_url  #
        #     self.video_page_conmon_url = course.video_page_conmon_url
        #
        #     self.course_video_page_url = course.course_video_page_url
        #     self.live_video_page_url = course.live_video_page_url
        #
        #     self.course_video_list = course.course_video_list  # 保存UCASVideo列表
        #     self.live_video_list = course.live_video_list
        #
        #     # 视频多页的情况
        #     self.course_video_current_page = course.course_video_current_page
        #     self.live_video_current_page = course.live_video_current_page

class UCASCourseDownloader(object):
    def __init__(self, time_out = 5, check_version = False):
        self.__BEAUTIFULSOUPPARSE = 'html.parser'  # or use 'lxml'
        self.semester = None
        self.is_download_record_video = False
        self.is_download_live_video = False
        self.save_base_path, self.semester, self.is_download_record_video, self.is_download_live_video = UCASCourseDownloader._read_info_from_file()
        self.session = None
        self.headers = None
        self._init_session()
        self.course_site_list = []
        self.video_site_list = [] #这是一个课程视频tuple的list，每个元素中包含录播地址和直播地址
        self.to_download_resource = []
        self.to_download_u3m8_video = []
        self.lock = multiprocessing.Lock()
        self._time_out = time_out
        self.version = '1.4'
        self.check_version = check_version

    def _check_version(self):
        r = requests.get('https://api.github.com/repos/youqingxiaozhua/Ucas_course_ppt_auto_download/releases/latest')
        github_latest = json.loads(r.text)
        version = github_latest['name']
        version_note = github_latest['body']
        if version != self.version:
            print('\nA new version (v%s: %s) have been released, please download from this link:' % (version, version_note))
            print('https://github.com/youqingxiaozhua/Ucas_course_ppt_auto_download/releases\n')

    def _init_session(self):
        t = LoginUCAS().login_sep()
        self.session = t.session
        self.headers = t.headers

    @classmethod
    def _read_info_from_file(cls):
        with codecs.open('./private.txt', "r", "utf-8") as f:
            save_base_path = semester = None
            is_download_record_video = False
            is_download_live_video = False
            for i, line in enumerate(f):
                if i < 2: continue
                if i == 2:
                    save_base_path = line.strip()
                if i == 3:
                    semester = line.strip()
                if i == 4:
                    is_download_record_video = line.strip() == 'true'
                if i == 5:
                    is_download_live_video = line.strip() == 'true'
        return save_base_path, semester, is_download_record_video, is_download_live_video

    def _get_course_page(self):
        # 从sep中获取Identity Key来登录课程系统，并获取课程信息
        url = "http://sep.ucas.ac.cn/portal/site/16/801"
        r = self.session.get(url, headers=self.headers)
        url = re.findall(r'<meta http-equiv="refresh" content="0;url=([^"]*)">', r.text)[0]

        self.headers['Host'] = "course.ucas.ac.cn"
        html = self.session.get(url, headers=self.headers).text
        return html

    def _parse_course_list(self):
        # 获取课程的所有URL
        html = self._get_course_page()
        #获得每个课程页面的url，即https://course.ucas.ac.cn/portal/site/ + 数字
        self.course_site_list = ['https://course.ucas.ac.cn/portal/site/' + x for x in
                                 re.findall(r'https://course.ucas.ac.cn/portal/site/([\d]+)"', html)]

    def _get_course_base_info_list(self) ->list:
        # 获取课程的所有URL
        html = self._get_course_page()
        course_id_list = re.findall(r'https://course.ucas.ac.cn/portal/site/([\d]+)"', html)

        course_list = []
        for index in range(course_id_list.__len__()):
            course_site_url = 'https://course.ucas.ac.cn/portal/site/' + course_id_list[index]
            resource_page_url = 'https://course.ucas.ac.cn/access/content/group/'+ course_id_list[index]

            try:
                html = self.session.get(course_site_url, headers=self.headers).text
                html = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE)

                #查找并遍历所有的a标签，查找完整的课程名
                a_tag_list = html.find_all('a')
                title_text = ''
                for a_tag in a_tag_list:
                    temp_text = a_tag.get("href")
                    if temp_text and course_site_url in temp_text:  # 包含标题的a标签，包含该课程的基址
                        title_text = a_tag.get("title")
                        break

                if self.semester not in title_text: #学期过滤
                    # print("not in " + title_text)
                    continue

                course = UCASCourse(title_text, course_site_url)
                course.resource_page_url = resource_page_url

                a_tag_list = html.find_all('a')
                for a_tag in a_tag_list:
                    if '课程视频' in a_tag.text:# 查询并保存某课程视频所在的网站基址
                        # play_video_base_url = a_tag.get("href") + "/video"
                        # self.video_site_list.append(play_video_base_url)
                        course.video_page_conmon_url = a_tag.get("href") + "/video"
                        break

                course_list.append(course)
            except Exception as e:
                print('Error-----------课程信息获取失败，未知错误: ', course_site_url)
        return course_list

    def _get_all_resource_url(self):
        # 从课程的所有URL中获取对应的所有课件
        course_base_url = 'https://course.ucas.ac.cn/access/content/group/' #这个链接可以获得文件的列表...很特殊的链接
        urls = [course_base_url + x.split('/')[-1] + '/' for x in self.course_site_list]
        list(map(self._get_resource_url, urls))

    def _get_resource_url(self, base_url, _path='', source_name=None):
        html = self.session.get(base_url, headers=self.headers).text
        tds = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE).find_all('li')
        if not source_name:
            source_name = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE).find('h3').text
            if self.semester and source_name.find(self.semester) == -1:
                return  # download only current semester
        res = set()
        for td in tds:
            url = td.find('a')
            if not url: continue
            url = urllib.parse.unquote(url['href'])
            if url == '../': continue
            # if 'Folder' in td.text:  # directory
            if 'folder' in td.attrs['class']:  # directory
                # folder_name = td.text
                self._get_resource_url(base_url + url, _path + '/' + url, source_name)
            if url.startswith('http:__'):  # Fix can't download when given a web link. eg: 计算机算法分析与设计
                try:
                    res.add((self.session.get(base_url + url, headers=self.headers, timeout=self._time_out).url, _path))
                except requests.exceptions.ReadTimeout:
                    print("Error-----------: ", base_url + url, "添加进下载路径失败,服务器长时间无响应")
                except Exception as e:
                    print("Error-----------: ", base_url + url, "添加进下载路径失败,未知错误")
            else:
                res.add((base_url + url, _path))

        for url, _path in res: #存储课程名称和每个课件的url
            self.to_download_resource.append((source_name, _path, url))

    def _get_u3m8_url_form_url(self, video_play_url:'str') ->str: #从视频播放地址获取u3m8地址
        html = self.session.get(video_play_url, headers=self.headers).text
        html = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE)
        u3m8_url = html.find_all('source')[0].get("src")
        return u3m8_url

    def _get_all_course_video(self, video_list_base_url: 'str', page_number = 1) ->list:
        course_video_list = []
        has_next_page = False #标记是否有下一页
        #对视频进行解析，解析出UCASVideo列表
        video_list_url = video_list_base_url + '/list' + '/' + '?pageNum=' + str(page_number)
        html = self.session.get(video_list_url, headers = self.headers).text
        html = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE)
        a_tag_list = html.find_all('a')
        for a_tag in a_tag_list:  # 遍历所有的a标签，查找某个视频播放的hash地址，并获得u3m8地址
            if a_tag.text == '下一页':#有下一页
                has_next_page = True
            temp_text = a_tag.get("onclick")
            if not temp_text or not 'gotoPlay' in temp_text:  # 查询并保存某课程视频所在的网站基址
                continue
            # 获取视频地址的hash值
            video_hash = re.findall("gotoPlay\(\'(.*?)\'", temp_text)[0]
            video_name = a_tag.get("title")
            # 拼接观看地址
            play_video_url = video_list_base_url + '/play?id=' + video_hash + '&type=u'
            # 需要从play_video_url获取到u3m8地址
            play_video_u3m8_url = self._get_u3m8_url_form_url(play_video_url)

            video_object = UCASVideo(video_name, play_video_u3m8_url)
            course_video_list.append(video_object)

        #需要处理可能存在的多页情况
        if has_next_page:
            course_video_list = course_video_list + self._get_all_course_video(video_list_base_url, page_number + 1)
        return course_video_list

    def _get_live_info_list(self, special_time_record_list_url: 'str', page_number = 1) ->list:
        video_info_set = set()
        has_next_page = False
        html = self.session.get(special_time_record_list_url, headers=self.headers).text
        html = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE)

        a_tag_list = html.find_all('a')
        for a_tag in a_tag_list:  # 从中提取出各个视频的信息
            if a_tag.text == '下一页':#有下一页
                has_next_page = True

            temp_text = a_tag.get("onclick") # 如，gotoPlay('21067','2');return false;
            if not temp_text or not 'gotoPlay' in temp_text:
                continue

            video_id = temp_text.split('\'')[1] #如，分离出21076
            video_name = temp_text.split('\'')[3]
            video_info_set.add((video_id, video_name))

        if has_next_page:
            video_info_set = video_info_set.union(self._get_live_info_list(special_time_record_list_url, page_number + 1))
        return list(video_info_set)

    def _get_all_live_video(self, video_list_base_url: 'str', page_number = 1) ->list:
        course_video_list = []
        has_next_page = False #标记是否有下一页
        #对视频进行解析，解析出UCASVideo列表

        # 获得课程id
        site_id = video_list_base_url.split('/')[5] # 如，'https://course.ucas.ac.cn/portal/site/173977/tool/0ce5bb50-3042-4f04-b74f-700ef8f4d793/video'

        video_dir_list_url = video_list_base_url + '/recordPage' + '/' + '?pageNum=' + str(page_number)
        html = self.session.get(video_dir_list_url, headers = self.headers).text
        html = BeautifulSoup(html, self.__BEAUTIFULSOUPPARSE)
        a_tag_list = html.find_all('a')
        for a_tag in a_tag_list:  # 遍历所有的a标签，查找某个视频播放的hash地址，并获得u3m8地址
            if a_tag.text == '下一页':#有下一页
                has_next_page = True
            temp_text = a_tag.get("onclick")
            if not temp_text or not 'gotoList' in temp_text:
                continue
            if a_tag.get("title") != a_tag.text: # 过滤掉重复的直播时间，只保留文本中的日期
                continue
            # 获取直播的日期
            record_time = a_tag.get("title")

            special_time_record_list_url = video_list_base_url + '/recordList?siteId=' + site_id + '&recordingTime=' + record_time

            special_time_live_video_info_list =  self._get_live_info_list(special_time_record_list_url)#一个二元组list
            for video_info in special_time_live_video_info_list:
                video_id = video_info[0]
                video_name = video_info[1]

                # 拼接观看地址
                play_video_url = video_list_base_url + '/play?id=' + video_id + '&type=r&rank=' + video_name
                # 需要从play_video_url获取到u3m8地址
                play_video_u3m8_url = self._get_u3m8_url_form_url(play_video_url)

                video_object = UCASVideo(video_name, play_video_u3m8_url, record_time + '/')
                course_video_list.append(video_object)

        #需要处理可能存在的多页情况
        if has_next_page:
            course_video_list = course_video_list + self._get_all_course_video(video_list_base_url, page_number + 1)
        return course_video_list

    #添加某课程的全部视频后返回
    def _add_to_course_all_course_video(self, course: 'UCASCourse') -> UCASCourse:

        if self.is_download_record_video:
            #录播视频
            course_video_list = self._get_all_course_video(course.video_page_conmon_url)
            course.course_video_list = course_video_list

        if self.is_download_live_video:
            #直播视频
            live_video_list = self._get_all_live_video(course.video_page_conmon_url)
            course.live_video_list = live_video_list

        return course

    def _download_resource(self, param):#资源下载的程序
        # 下载文件
        dic_name, sub_directory, url = param #课程名称， 子目录名称（默认为空）， 课件完整url
        save_path = self.save_base_path + '/' + dic_name + '/' + sub_directory #保存目录
        with self.lock:
            if not os.path.exists(save_path):  # To create directory
                os.makedirs(save_path)

        filename = url.split('/')[-1]
        save_path += '/' + filename
        if not os.path.exists(save_path):  # To prevent download exists files
            try:
                r = self.session.get(url, stream=True, timeout=self._time_out)
            except requests.exceptions.ReadTimeout as e:
                print('Error-----------文件下载失败,服务器长时间无响应: ', save_path)
            except Exception as e:
                print('Error-----------文件下载异常,未知错误: ', save_path)

            try:
                # HTML file does not have Content Length attr
                size_mb = int(r.headers.get('Content-Length')) / (1024 ** 2)
            except TypeError:
                size_mb = 0.33  # html文件直接指定大小 :)
            try:
                # print('Start download {dic_name}  >> {sub_directory}{filename}  {size_mb:.2f}MB'.format(**locals()))
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                            f.flush()

                print('Done-----------文件下载成功: ', dic_name + ' "' + filename + '"')
                # print('{dic_name}  >> {sub_directory}{filename}   Download success'.format(**locals()))
            # except UnicodeEncodeError:
            except Exception as e:
                print('Error-----------文件下载失败，请重试: ', dic_name + ' "' + filename + '"')
                # print('{dic_name}  >> {sub_directory} Download a file'.format(**locals()))

    def _download_course_video(self, param:'tuple'):
        dic_name, sub_directory, video_name, video_m3u8_url = param  # 课程名称， 子目录名称（默认为空），视频名称，课件完整u3m8地址
        save_path = self.save_base_path + '/' + dic_name + '/录播视频' + '/' + sub_directory  # 保存目录
        with self.lock:
            if not os.path.exists(save_path):  # To create directory
                os.makedirs(save_path)

        temp_path = save_path + '/' + video_name + '.mp4' #如果这里加双引号，则下一行的路径判断出错
        if os.path.exists(temp_path):  # To prevent download exists files
            print('Warn-----------视频已存在: ', dic_name + ' "' + video_name + '.mp4"')
            return

        # 需要提前下载配置ffmpeg
        ffmpeg_command = 'ffmpeg -i ' + video_m3u8_url + ' -c copy ' + save_path + '/"' + video_name + '.mp4"'
        # 只打印下载结果
        try:
            proc = subprocess.Popen(
                ffmpeg_command,
                shell = True,
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                # universal_newlines = True,
                bufsize = -1
            )
            stdout, stderr = proc.communicate()  # 等待完成

            print('Done-----------视频下载成功: ', dic_name + ' "' + video_name + '.mp4"')
        except Exception as e: #错误捕获是失败的，有错误也获取不到
            print('Error-----------视频下载失败，请重试: ', dic_name + ' "' + video_name + '.mp4"')
        return

    def _download_live_video(self, param:'tuple'):
        dic_name, sub_directory, video_name, video_m3u8_url = param  # 课程名称， 子目录名称（默认为空），视频名称，课件完整u3m8地址
        save_path = self.save_base_path + '/' + dic_name + '/直播视频' + '/' + sub_directory  # 保存目录
        with self.lock:
            if not os.path.exists(save_path):  # To create directory
                os.makedirs(save_path)

        temp_path = save_path + '/' + video_name + '.mp4'  # 如果这里加双引号，则下一行的路径判断出错
        if os.path.exists(temp_path):  # To prevent download exists files
            print('Warn-----------视频已存在: ', dic_name + ' ' + sub_directory + ' "' + video_name + '.mp4"')
            return

        # 需要提前下载配置ffmpeg
        ffmpeg_command = 'ffmpeg -i ' + video_m3u8_url + ' -c copy ' + save_path + '/"' + video_name + '.mp4"'
        # 只打印下载结果
        try:
            proc = subprocess.Popen(
                ffmpeg_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # universal_newlines = True,
                bufsize=-1
            )
            stdout, stderr = proc.communicate()  # 等待完成

            print('Done-----------视频下载成功: ', dic_name + ' ' + sub_directory + ' "' + video_name + '.mp4"')
        except Exception as e:  # 错误捕获是失败的，有错误也获取不到
            print('Error-----------视频下载失败，请重试: ', dic_name + ' ' + sub_directory + ' "' + video_name + '.mp4"')
        return

    def _download(self, course:'UCASCourse'):
        #下载课件，暂时略

        #下载视频
        #下载录播视频
        if course.course_video_list.__len__():
            # 课程名称， 子目录名称（默认为空），视频名称，课件完整u3m8地址
            dic_name = course.name
            sub_directory = ''
            live_video_list = course.course_video_list

            dic_name_list = [dic_name for index in range (live_video_list.__len__())]
            sub_directory_list = [sub_directory for index in range(live_video_list.__len__())]
            video_name_list = [live_video_list[index].name for index in range(live_video_list.__len__())]
            u3m8_url_list = [live_video_list[index].u3m8_url for index in range(live_video_list.__len__())]

            # 开启线程池，每个视频一个，最大可能并行化
            param_list = [
                (dic_name_list[index], sub_directory_list[index], video_name_list[index], u3m8_url_list[index])
                for index in range (live_video_list.__len__())
            ]

            live_video_download_pool = Pool()
            live_video_download_pool.map(self._download_course_video, param_list)
            # live_video_download_pool.map(self._download_course_video, dic_name_list, sub_directory_list,
            #                                video_name_list, u3m8_url_list)
            live_video_download_pool.close()
            live_video_download_pool.join()

        #下载直播视频
        if course.live_video_list.__len__():
            # 课程名称， 子目录名称（默认为空），视频名称，课件完整u3m8地址
            dic_name = course.name
            sub_directory = ''
            live_video_list = course.live_video_list

            dic_name_list = [dic_name for index in range (live_video_list.__len__())]
            sub_directory_list = [live_video_list[index].dir_name for index in range(live_video_list.__len__())]
            video_name_list = [live_video_list[index].name for index in range(live_video_list.__len__())]
            u3m8_url_list = [live_video_list[index].u3m8_url for index in range(live_video_list.__len__())]

            # 开启线程池，每个视频一个，最大可能并行化
            param_list = [
                (dic_name_list[index], sub_directory_list[index], video_name_list[index], u3m8_url_list[index])
                for index in range (live_video_list.__len__())
            ]

            live_video_download_pool = Pool()
            live_video_download_pool.map(self._download_live_video, param_list)
            # live_video_download_pool.map(self._download_course_video, dic_name_list, sub_directory_list,
            #                                video_name_list, u3m8_url_list)
            live_video_download_pool.close()
            live_video_download_pool.join()

        return

    def start(self):
        #暂时不需要检查版本了
        # if self.check_version:
        #     self._check_version()

        #待后续整合部分 begin
        self._parse_course_list()

        print('读取课件中......')
        self._get_all_resource_url()
        print('读取课件信息完成。')

        print('开始下载课件......')
        course_pool = Pool()
        course_pool.map(self._download_resource, self.to_download_resource)
        course_pool.close()
        course_pool.join()
        print('下载课件完成。')
        # 待后续整合部分 end

        # 开发中 begin
        course_base_info_list = self._get_course_base_info_list()
        course_full_info_list = course_base_info_list  # 包含课件信息的课程列表，需要后续处理

        if not (self.is_download_live_video or self.is_download_record_video):
            return

        print('读取视频中......')

        #下面两句如何合并，则会出错
        course_full_info_list_include_video = list(
            map(self._add_to_course_all_course_video, course_full_info_list)
        )  # 包含视频信息的课程列表
        course_full_info_list = course_full_info_list_include_video

        print('读取视频信息完成。')
        print('开始下载视频......')
        list(map(self._download, course_full_info_list))

        # 开发中 end

if __name__ == '__main__':
    base_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_path)
    start = datetime.now()

    s = UCASCourseDownloader()
    s.start()

    print('资源下载全部完成, 共计用时:', datetime.now() - start)
    os.system("pause")
