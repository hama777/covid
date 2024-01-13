#!/usr/bin/python
# -*- coding: utf-8 -*-
# https://qiita.com/ryo-ma/items/20db8cd20f1086838249

import os
import requests
import datetime
import pandas as pd

from ftplib import FTP_TLS
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from datetime import datetime as dt

version = "3.08"

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
appdir = os.path.dirname(os.path.abspath(__file__))

#  日々のデータ
pref_url = "https://covid19.mhlw.go.jp/public/opendata/newly_confirmed_cases_daily.csv"

templatefile  = appdir + "\\template.htm"
resultfile  = appdir + "\\index.htm"
conffile = appdir + "\\covid.conf"
datafile = appdir + "\\daily.csv"   #  過去のデータ  日付\t全国\t兵庫県
areafile = appdir + "\\area.txt"   #  対象エリア   エリア名\t都道府県名\t都道府県名 ...
popufile = appdir + "\\population.txt"   # 人口データ    都道府県名\t人口
ftp_host = ftp_user = ftp_pass = ftp_url =  ""
out = ""
lastdate = ""    #   最新の日付

df = ""
df_target = ""
covid_info = []  # 取得したデータ  県名、本日感染者数、累積、前週間平均、週間平均
popu = {}      #  キー  都道府県名  値  人口
target = {}    #  キー  エリア名  値  都道府県名のリスト
debug = 0      #  1 はデバッグモード  ftpはしない
area_index = {}   #  各都道府県の列名

def main_proc() :

    #  事前処理
    read_population()
    read_areadata()
    read_config()
    download_data()

    #  メイン処理
    get_target_info()  #  目的地域の処理
    template()         #  html出力
    ftp_upload()       #  アップロード

#   人口、列名データの読み込み
def read_population() :
    global popu,area_index
    f = open(popufile , 'r', encoding='utf-8')
    for line in f :
        line = line.replace("\n","")
        data = line.split("\t")   
        popu[data[0]] = data[1]         # 人口
        area_index[data[0]] = data[2]   # 列名
    f.close()

#   計測するの地域データの読み込み
def read_areadata() :
    global target
    f = open(areafile , 'r', encoding='utf-8')
    for line in f :
        line = line.replace("\n","")
        data = line.split("\t")   
        pref = data[1:]      # 2番目以降  県名リストを取り出す
        target[data[0]] = pref
    f.close

#   計測するの地域の情報取得
def get_target_info() :
    global df

    df = pd.read_csv(datafile,index_col=0,parse_dates=True, header=0)
    for target_name,pref_list in target.items() :
        create_dataf(pref_list)
        area_info(target_name,pref_list)

#   計測するの地域のdataframeを作成する
def create_dataf(pref_list):
    global df_target       # 結果のdataframe

    for i,pref_name in enumerate(pref_list) :
        index = area_index[pref_name]
        if i == 0 :
            df_target =  df[index]
        else :
            df_target = df_target + df[index]

#   計測するの各地域の処理
def area_info(area_name,pref_list) :
    global  covid_info

    get_lastdate()
    target_popu = calc_population(pref_list)    # 対象となる地域の人口
    areadata = df_target
    posi = areadata.iloc[-1]       #   最新データの感染者数
    accposi = areadata.sum()       #   感染者累計数

    #  前日から1週間のデータ取得
    cweek = cur_week_mean(areadata)
    pweek = prev_week_mean(areadata,13,7) 
    p2week = prev_week_mean(areadata,21,14) 

    # ランク
    rank = get_rank(areadata)
    
    wk1data,we1date = get_ndaysago_data(areadata,8)   #  1週間前のデータ
    wk2data,we2date = get_ndaysago_data(areadata,15)   #  2週間前のデータ
    weekly = "{0} {1},{2} {3}".format(we2date,wk2data,we1date,wk1data)
    #print("weekly = " + weekly)

    area_list = []
    area_list.append(area_name)
    area_list.append(posi)
    area_list.append(accposi)
    area_list.append(pweek)
    area_list.append(cweek)
    area_list.append(p2week)
    area_list.append(rank)
    area_list.append(weekly)
    area_list.append(target_popu)
    
    covid_info.append(area_list)

#   データのダウンロード
def download_data() :
    if debug == 1 :
        return 

    urlData = requests.get(pref_url).content
    with open(datafile ,mode='wb') as f: # wb でバイト型を書き込める
        f.write(urlData)    

#   データの最終日を求める
def get_lastdate():
    global  lastdate    # データの最終日

    lastdata = df.tail(1)
    laststr = str(lastdata.index.values)
    lastdate = dt.strptime(laststr[2:12], '%Y-%m-%d')  #   最新データの日付

#   pref_list の都道府県の人口合計を返す
def calc_population(pref_list) :
    ans = 0 
    for name in pref_list :
        ans = ans + int(popu[name])
    return ans

def get_rank(areadf) :
    r = areadf.rank(ascending=False)
    return r.iloc[-1]

def create_info_table() :
    max_col = 3               # 横に何列並べるか
    block_count = 0 

    for data  in covid_info:
        area_name = data[0]   #  地域名
        population = int(data[8]  )  #  人口
        posi = data[1]        #  感染者数
        accposi = data[2]     #  累積感染者数
        pweek = data[3]       #  1週間前の週間平均
        cweek = data[4]
        p2week = data[5]      #  2週間前の週間平均
        rank = data[6]        #  順位
        weekly = data[7]        #  週ごとのデータ
        inc_rate = cweek / pweek    #  今週と1週間前の倍率
        inc_rate2 = pweek / p2week    #  1週間前と2週間前の増減率
        diff_rate = inc_rate - inc_rate2       #  増減率の差分ポイント

        if block_count % max_col == 0 :
            out.write("<div class='flex'>")

        out.write("<div class='frame'><table>")
        out.write("<tr  class='area'><td class='hd'>地域</td><td class='hd2'>{}</td></tr>\n".format(area_name))   #   県名
        out.write("<tr><td>本日感染者数</td><td>{}</td></tr>\n".format( posi))
        out.write("<tr><td>累積感染者数</td><td>{}</td></tr>\n".format(accposi))
        out.write("<tr><td>人口比率</td><td>{0:2.3f} %</td></tr>\n".format( accposi/population*100))
        out.write("<tr><td>前週平均</td><td>{0:3.1f}</td></tr>\n".format(pweek))
        out.write("<tr><td>週平均(10万人当)</td><td>{0:3.1f} ({1:3.1f})</td></tr>\n".format(cweek,cweek*7/population*100000))
        out.write("<tr><td>週倍率 (増減)</td><td>{0:4.2f}倍 ({1:4.2f}) </td></tr>\n".format(inc_rate,diff_rate))
        out.write("<tr><td>順位</td><td>{0:4.0f}  </td></tr>\n".format(rank))
        out.write("<tr><td>同曜日データ</td><td>{}  </td></tr>\n".format(weekly))
        out.write("</table></div><br>\n")

        if block_count % max_col == (max_col-1) :
            out.write("</div>")       # flex の終了
        block_count +=1 


def get_ndaysago_data(dataf,n):          # n日前の感染者データと日付を返す
    ndaysago = dataf.iat[-n]
    d1 = str(dataf.index[-n] )[5:10]
    d1 = d1.replace("-","/")     #  08-01  ->  08/01
    return  ndaysago,d1

def prev_week_mean(dataf,start,end)   :
    startday  = lastdate - datetime.timedelta(days=start)
    endday = lastdate - datetime.timedelta(days=end)
    week = dataf[startday : endday]
    return  week.mean()   # 前日から1週間の平均

def cur_week_mean(dataf)   :
    startday  = lastdate - datetime.timedelta(days=6)
    endday = lastdate
    week = dataf[startday : endday]
    #print(week.mean()[0])
    return  week.mean()   # 前日から1週間の平均

def read_config() : 
    global ftp_host,ftp_user,ftp_pass,ftp_url,debug

    if not os.path.isfile(conffile) :
        debug = 1 
        return    
    conf = open(conffile,'r', encoding='utf-8')
    ftp_host = conf.readline().strip()
    ftp_user = conf.readline().strip()
    ftp_pass = conf.readline().strip()
    ftp_url = conf.readline().strip()
    conf.close()

def ftp_upload() : 
    if debug == 1 :
        return 
    with FTP_TLS(host=ftp_host, user=ftp_user, passwd=ftp_pass) as ftp:
        ftp.storbinary('STOR {}'.format(ftp_url), open(resultfile, 'rb'))

def template() :
    global out 
    f = open(templatefile , 'r', encoding='utf-8')
    out = open(resultfile,'w' ,  encoding='utf-8')
    for line in f :
        if "%curdate%" in line :
            curdate(line)
            continue
        if "%info_table%" in line :
            create_info_table()
            continue
        if "%today%" in line :
            today(line)
            continue
        out.write(line)

    f.close()
    out.close()

#   日付を yyyymmdd 形式から yyyy/mm/dd 形式に変換
def curdate(s):
    d = str(lastdate)
    yy = d[0:4]
    mm = d[5:7]
    dd = d[8:10]
    out.write(s.replace("%curdate%","{0}/{1}/{2}".format(yy,mm,dd)))

#   現在日時  取得  
def today(s):
    d = datetime.datetime.today().strftime("%m/%d %H:%M")
    s = s.replace("%today%",d)
    out.write(s)

# ----------------------------------------------------------
main_proc()
