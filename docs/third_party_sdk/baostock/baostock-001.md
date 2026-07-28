# BaoStock SDK 文档 · 分片 001

> 本分片包含第 1–10 份文档。导航：[返回总索引](index.md)。

## 本分片目录

1. [平台介绍](#baostock-document-001)
2. [Python API文档](#baostock-document-002)
3. [A股K线数据](#baostock-document-003)
4. [每日更新](#baostock-document-004)
5. [PY开发资源](#baostock-document-005)
6. [指数数据](#baostock-document-006)
7. [估值指标(日频)](#baostock-document-007)
8. [除权除息信息](#baostock-document-008)
9. [复权因子信息](#baostock-document-009)
10. [本地计算前复权](#baostock-document-010)

---

<a id="baostock-document-001"></a>

## 1. 平台介绍

> 官方页面：[home.md](https://baostock.com/mainContent?file=home.md)

<table style="border-collapse:collapse; margin:0 auto; border:none;">
  <tr>
    <td style="background:#fff; text-align:center; padding:2px; border:none;">
      <img src="https://baostock.com/helpdocs/img/md/huodong.png" style="height:150px;" onerror="this.src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='"/>
    </td>
    <td style="background:#fff; text-align:center; padding:2px; border:none;">
      <img src="https://baostock.com/helpdocs/img/md/QQ.png" style="height:150px;" onerror="this.src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='"/>
    </td>
  </tr>
  <tr>
    <td style="background:#fff; text-align:center; padding:2px; border:none;">
      <strong style="font-size:17px;">Baostock业务交流群 (可咨询PTrade)</strong>
    </td>
    <td style="background:#fff; text-align:center; padding:2px; border:none;">
      <strong style="font-size:17px;">Baostock官方技术服务QQ群:<b>767012112</b> (问题解答 技术交流)</b></strong>
    </td>
  </tr>
</table>

<p style="margin:0;padding:0;line-height:1.2;"><strong style="font-size:24px;">平台介绍</strong></p>

**证券宝`www.baostock.com`**是一个**免费、开源**的**证券数据平台**（无需注册）。
* 提供大量准确、完整的证券历史行情数据、上市公司财务数据等。
* 通过python API获取证券数据信息，满足量化交易投资者、数量金融爱好者、计量经济从业者数据需求。
* 返回的数据格式：
  * pandas DataFrame类型，以便于用pandas/NumPy/Matplotlib进行数据分析和可视化。
  * 同时支持通过BaoStock的数据存储功能，将数据全部保存到本地后进行分析。
* 支持语言：目前版本BaoStock.com目前只支持**Python3.6**或**Python3.9**及以上(暂不支持python 2.x)。
* 持续更新：BaoStock.com还在不断的完善和优化，后续将逐步增加港股、期货、外汇和基金等方面的金融数据，为成为一个免费金融数据平台努力。
* 分享优化：请通过微信、网站博客或者知乎文章等方式分享给大家，使它能在大家的使用过程中逐步得到改进与提升，以便于更好地为大家提供免费服务。
* 平台麦克：证券宝BaoStock.com从发布到现在，已经帮助很多用户在数据方面减轻了工作量，同时也得到很多用户的反馈。它将一如既往的以免费、开源的形式分享出来，希望给有需要的朋友带来一些帮助。
**联系方式：Baostock官方技术QQ群：767012112 (问题解答、技术交流)；EMail:`baostock@163.com`。**
免费证券数据平台证券宝`www.baostock.com`会逐步分享证券投资文章、投资观点及教程，希望能够帮助大家！


#### 下载安装

##### 方式1：pip install baostock
使用指定源安装：
```python
pip install baostock -i https://pypi.org/simple 
```

##### 方式2：访问 [https://pypi.python.org/pypi/baostock](https://pypi.python.org/pypi/baostock) 下载安装
```python
python setup.py install或pip install xxx.whl
```
**注意：程序运行时，文件名、文件夹名不能是baostock。**

#### 版本升级
```
 pip install --upgrade baostock -i https://pypi.org/simple 
```

**使用前提：**

安装Python

安装pandas（pip install pandas）

建议安装Anaconda，以免出现问题（Anaconda是一个开源的Python发行版本，其包含了conda、Python等180多个科学包及其依赖项，下载地址`https://www.anaconda.com/download/`）。

#### 每日最新数据更新时间：

* 当前交易日**17:30**，完成日K线数据入库；
* 当前交易日**18:00**，完成复权因子数据入库；
* 当前交易日**20:00**，完成分钟K线数据入库；
* 第二自然日**1:30**，完成前交易日“其它财务报告数据”入库；
* 周六**17:30**，完成周K线数据入库；
* 每月1号**17:30**，完成上月月K线数据入库；

#### 每周数据更新时间：

* 每周一下午，完成上证50成份股、沪深300成份股、中证500成份股信息数据入库；

#### 数据范围说明

##### 股票数据

* 日、周、月K线数据，时间范围：1990-12-19至今。
* 5、15、30、60分钟K线数据，时间范围（近5年）：2020-01-03至今。

##### ETF数据

* 日、周、月K线数据，时间范围：2026-01-05至今。
* 5、15、30、60分钟K线数据，时间范围：2026-01-05至今。

##### 指数数据

* 日、周、月K线已经包含指数(不提供分钟K线数据)：综合指数，规模指数，一级行业指数，二级行业指数，策略指数，成长指数，价值指数，主题指数，基金指数，债券指数。
* 时间范围：2006-01-01至今。

##### 季频财务数据

* 已经包含的财务数据：部分上市公司资产负债信息、上市公司现金流量信息、上市公司利润信息、上市公司杜邦指标信息。
* 时间范围：2007年至今。

##### 季频公司报告

* 上市公司业绩预告信息，时间范围：2003年至今。
* 上市公司业绩快报信息，时间范围：2006年至今。

#### 版本信息


##### V0.9.3版本 2026/07/10
* 新增“每日更新”相关的API，query_daily_history_k_AStock()、query_daily_history_k_ETF()、query_daily_adjust_factor()。
 
##### V0.9.2版本 2026/06/06

* 减少每批次获取数据的步长，缩短服务器返回数据的反馈时间。 


##### V0.9.1版本 2026/04/15

* 支持多节点服务请求。

##### V0.8.9版本 2024/05/31

* 修复退出时socket未关闭问题；调整Demo程序的位置。

##### V0.8.8版本 2019/01/25

* 新增接口get\_data()，返回dataframe格式数据。

##### V0.8.7版本 2018/12/14

* 优化服务器、客户端之间的网络传输。

##### V0.8.5版本 2018/12/7

* 新增2019年交易日数据。

##### V0.8.5版本 2018/11/27

* 新增2006年01月-2018年09月指数成分股数据。

##### V0.8.5版本 2018/10/15

* 新增2006-2010年，日、周、月K线数据。

##### V0.8.5版本 2018/9/14

* 新增2011年，5分钟、15分钟、30分钟、60分钟、日、周、月K线数据。
* 新增“行业分类”接口：query\_stock\_industry()。
* 新增“上证50成分股”接口：query\_sz50\_stocks()。
* 新增“沪深300成分股”接口：query\_hs300\_stocks()。
* 新增“中证500成分股”接口：query\_zz500\_stocks()。

##### V0.8.1版本 2018/8/10

* 新增2012、2013年，5分钟、15分钟、30分钟、60分钟、日、周、月K线数据。
* 增强“历史A股K线数据”接口：query\_history\_k\_data()，添加周、月线前后复权功能。
* 增强“证券代码查询”接口：query\_all\_stock()，查询结果添加证券名称。
* 增强“季频盈利能力”接口：query\_profit\_data()，查询结果添加总股本(totalShare)、流通股本(liqaShare)。

##### V0.8.0版本 2018/7/27

* 新增“证券基本资料”接口query\_stock\_basic()。
* 新增“存款利率”接口query\_deposit\_rate\_data()，提供1990年至今数据。
* 新增“贷款利率”接口query\_loan\_rate\_data()，提供1990年至今数据。
* 新增“存款准备金率”接口query\_required\_reserve\_ratio\_data()，提供1999年至今数据。
* 新增“货币供应量”接口query\_money\_supply\_data\_month()，提供1978年至今数据。
* 新增“货币供应量(年底余额)”接口query\_money\_supply\_data\_year()，提供1952年至今数据。
* 新增“银行间同业拆放利率”接口query\_shibor\_data()，提供2006-10-08至今数据。

##### V0.7.6.03版本 2018/6/1

* 新增2014年，5分钟、15分钟、30分钟、60分钟、日、周、月K线数据。
* 新增2014年交易日信息。
* 优化登陆逻辑。

##### V0.7.6.02版本 2018/5/14

* 新增2015-2016交易日信息。
* 优化获取K线前后复权数据的性能。

##### V0.7.5版本 2018/4/20

* 增强接口“获取历史A股K线数据”：query\_history\_k\_data()，新增查询日K线、分钟线前后复权数据；周K线、月K线暂不支持。

##### V0.7.2版本 2018/4/13

* 新增接口“交易日查询”：query\_trade\_dates()，提供2017-2018年数据。
* 新增接口“证券代码查询”：query\_all\_stock()，提供2015年至今数据。

##### V0.7.0版本 2018/3/30

* 新增接口“盈利能力”接口query\_profit\_data()，提供2007至今的数据。
* 新增接口“营运能力”接口query\_operation\_data()，提供2007至今的数据。
* 新增接口“成长能力”接口query\_growth\_data()，提供2007至今的数据。
* 新增接口“偿债能力”接口query\_balance\_data()，提供2007至今的数据。
* 新增接口“现金流量”接口query\_cash\_flow\_data()，提供2007至今的数据。
* 新增接口“杜邦指标”接口query\_dupont\_data()，提供2007至今的数据。
* 新增接口“公司业绩快报”接口query\_performance\_express\_report()，提供2003至今的数据。
* 新增接口“公司业绩预告”接口query\_forcast\_report()，提供2006至今的数据。
* 新增web端下载示例数据。

##### V0.6.2版本 2018/3/16

* 新增'查询复权因子'接口query\_adjust\_factor()，提供1990至2017年数据。
* API性能优化，加快获取数据速度。
* 接口中忽略证券代码大小写。
* 接口中对指标参数大小写不敏感。
* 官网中提供搜索功能。

##### V0.6.1版本 2018/2/13

* 接口query\_history\_k\_data()，新增"d=日k线、w=周k线、m=月k线"2015-01-01至今的规模指数、一级行业指数、二级行业指数、策略指数、成长指数、价值指数、主题指数。
* 接口query\_history\_k\_data()，新增"d=日k线"滚动市盈率(peTTM)、市净率(pbMRQ)、滚动市销率(psTTM)、滚动市现率(pcfNcfTTM)。
* 接口query\_history\_k\_data()，新增指数、股票"d=日k线、w=周k线、m=月k线"的涨跌幅(pctChg)。
* 接口query\_history\_k\_data()，新增股票"d=日k线"的'是否ST(isST)'。
* 新增'查询除权除息信息'接口query\_dividend\_data()，提供1990年至2017年数据。

##### V0.5.5版本 2018/2/5

* 优化next()方法，获取大量数据时分批次获取。

##### V0.5.1版本 2018/1/11

* 新增获取历史K线数据接口query\_history\_k\_data()。
* 提供2015-01-01至今的上交所A股、深交所A股，上交所指数（综合指数）、深交所指数（综合指数）d=日k线、w=周k线、m=月k线、5=5分钟、15=15分钟、30=30分钟、60=60分钟k线数据。

---

<a id="baostock-document-002"></a>

## 2. Python API文档

> 官方页面：[pythonAPI.md](https://baostock.com/mainContent?file=pythonAPI.md)

##### Python API文档 

#### 目录
  
* [1 入门示例](#入门示例)
  + [1.1 HelloWorld](#HelloWorld)
* [2 登录](#登录)
  + [2.1 login()](#login)
* [3 登出](#登出)
  + [3.1 logout()](#logout)
* [4 获取历史A股K线数据](#获取历史A股K线数据)
  + [4.1 获取历史A股K线数据：query_history_k_data_plus()](#query_history_k_data_plus)
  + [4.2 历史行情指标参数](#历史行情指标参数)
* [5 查询除权除息信息](#查询除权除息信息)
  + [5.1 除权除息信息：query_dividend_data()](#query_dividend_data)
* [6 查询复权因子信息](#查询复权因子信息)
  + [6.1 复权因子：query_adjust_factor()](#query_adjust_factor)
* [7 查询季频财务数据信息](#查询季频财务数据信息)
  + [7.1 季频盈利能力：query_profit_data()](#query_profit_data)
  + [7.2 季频营运能力：query_operation_data()](#query_operation_data)
  + [7.3 季频成长能力：query_growth_data()](#query_growth_data)
  + [7.4 季频偿债能力：query_balance_data()](#query_balance_data)
  + [7.5 季频现金流量：query_cash_flow_data()](#query_cash_flow_data)
  + [7.6 季频杜邦指数：query_dupont_data()](#query_dupont_data)
* [8 查询季频公司报告信息](#查询季频公司报告信息)
  + [8.1 季频公司业绩快报：query_performance_express_report()](#query_performance_express_report)
  + [8.2 季频公司业绩预告：query_forecast_report()](#query_forecast_report)
* [9 证券基本资料](#证券基本资料)  
  + [9.1 证券基本资料：query_stock_basic()](#query_stock_basic)
* [10 获取证券元信息](#获取证券元信息)
  + [10.1 交易日查询：query_trade_dates()](#query_trade_dates)
  + [10.2 证券代码查询：query_all_stock()](#query_all_stock)
* [11 宏观经济数据](#宏观经济数据)
  + [11.1 存款利率：query_deposit_rate_data()](#query_deposit_rate_data)
  + [11.2 贷款利率：query_loan_rate_data()](#query_loan_rate_data)
  + [11.3 存款准备金率：query_required_reserve_ratio_data()](#query_required_reserve_ratio_data)
  + [11.4 货币供应量：query_money_supply_data_month()](#query_money_supply_data_month)
  + [11.5 货币供应量(年底余额)：query_money_supply_data_year()](#query_money_supply_data_year)
* [12 板块数据](#板块数据)
  + [12.1 行业分类：query_stock_industry()](#query_stock_industry)
  + [12.2 上证50成分股：query_sz50_stocks()](#query_sz50_stocks)
  + [12.3 沪深300成分股：query_hs300_stocks()](#query_hs300_stocks)
  + [12.4 中证500成分股：query_zz500_stocks()](#query_zz500_stocks)
* [13 示例程序](#示例程序)
  + [13.1 获取指定日期全部股票的日K线数据：query_history_k_data_plus()](#example_query_history_k_data_plus)

#### <a id="入门示例"></a>入门示例


##### <a id="HelloWorld"></a>HelloWorld

此篇为平台入门示例，安装baostock后，可导入包运行此示例。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_k_data.xlsx)

```python

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取历史K线数据 ####
# 详细指标参数，参见“历史行情指标参数”章节
rs = bs.query_history_k_data_plus("sh.600000",
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
    start_date='2017-06-01', end_date='2017-12-31', 
    frequency="d", adjustflag="3") #frequency="d"取日k线，adjustflag="3"默认不复权
print('query_history_k_data_plus respond error_code:'+rs.error_code)
print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
#### 结果集输出到csv文件 ####
result.to_csv("D:/history_k_data.csv", encoding="gbk", index=False)
print(result)

#### 登出系统 ####
bs.logout()


```

#### <a id="登录"></a>登录
##### <a id="login"></a>login()

方法说明：登录系统。

使用示例：lg = login()

返回信息：

* lg.error\_code：错误代码，当为“0”时表示成功，当为非0时表示失败；
* lg.error\_msg：错误信息，对错误的详细解释。


#### <a id="登出"></a>登出

##### <a id="logout"></a>logout()

方法说明：登出系统

使用示例：lg = logout()

返回信息：

* lg.error\_code：错误代码，当为“0”时表示成功，当为非0时表示失败；
* lg.error\_msg：错误信息，对错误的详细解释。


#### <a id="获取历史A股K线数据"></a>获取历史A股K线数据

##### <a id="query_history_k_data_plus"></a>获取历史A股K线数据：query\_history\_k\_data\_plus()

方法说明：通过API接口获取A股历史交易数据，可以通过参数设置获取日k线、周k线、月k线，以及5分钟、15分钟、30分钟和60分钟k线数据，适合搭配均线数据进行选股和分析。

返回类型：pandas的DataFrame类型。

能获取1990-12-19至当前时间的数据；

可查询不复权、**前复权**、**后复权**数据。

示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_A_stock_k_data.xlsx)

日线使用示例：

```python

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取沪深A股历史K线数据 ####
# 详细指标参数，参见“历史行情指标参数”章节；“分钟线”参数与“日线”参数不同。“分钟线”不包含指数。
# 分钟线指标：date,time,code,open,high,low,close,volume,amount,adjustflag
# 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
rs = bs.query_history_k_data_plus("sh.600000",
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
    start_date='2024-07-01', end_date='2024-12-31',
    frequency="d", adjustflag="3")
print('query_history_k_data_plus respond error_code:'+rs.error_code)
print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

#### 结果集输出到csv文件 ####   
result.to_csv("D:\\history_A_stock_k_data.csv", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```

分钟线使用示例：

```

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取沪深A股历史K线数据 ####
# 详细指标参数，参见“历史行情指标参数”章节；“分钟线”参数与“日线”参数不同。“分钟线”不包含指数。
# 分钟线指标：date,time,code,open,high,low,close,volume,amount,adjustflag
# 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
rs = bs.query_history_k_data_plus("sh.600000",
    "date,time,code,open,high,low,close,volume,amount,adjustflag",
    start_date='2024-07-01', end_date='2024-12-31',
    frequency="5", adjustflag="3")
print('query_history_k_data_plus respond error_code:'+rs.error_code)
print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

#### 结果集输出到csv文件 ####   
result.to_csv("D:\\history_A_stock_k_data.csv", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```

参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* fields：指示简称，支持多指标输入，以半角逗号分隔，填写内容作为返回类型的列。**详细指标列表见历史行情指标参数章节，日线与分钟线参数不同**。此参数不可为空；
* start：开始日期（包含），格式“YYYY-MM-DD”，为空时取2015-01-01；
* end：结束日期（包含），格式“YYYY-MM-DD”，为空时取最近一个交易日；
* frequency：数据类型，默认为d，日k线；d=日k线、w=周、m=月、5=5分钟、15=15分钟、30=30分钟、60=60分钟k线数据，不区分大小写；指数没有分钟线数据；周线每周最后一个交易日才可以获取，月线每月最后一个交易日才可以获取。
* adjustflag：**复权类型，默认不复权：3；1：后复权；2：前复权。已支持分钟线、日线、周线、月线前后复权。** BaoStock提供的是**涨跌幅复权算法**复权因子，具体介绍见：[BaoStock复权因子简介](https://baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf "BaoStock复权因子简介.pdf")。


**注意：**

* 股票停牌时，对于日线，开、高、低、收价都相同，且都为前一交易日的收盘价，成交量、成交额为0，换手率为空。

如果需要将换手率转为float类型，可使用如下方法转换：result["turn"] = [0 if x == "" else float(x) for x in result["turn"]]


**关于复权数据的说明：**

BaoStock使用“涨跌幅复权法”进行复权，详细说明参考上文“复权因子简介”。不同系统间采用复权方式可能不一致，导致数据不一致。

“涨跌幅复权法的”优点：可以计算出资金收益率，确保初始投入的资金运用率为100%，既不会因为分红而导致投资减少，也不会因为配股导致投资增加。

与同花顺、通达信等存在不同。

返回示例数据

| date       | code       | open  | high  | low   | close | preclose | volume    | amount     | adjustflag | turn     | tradestatus | pctChg     | isST |
|------------|------------|-------|-------|-------|-------|----------|-----------|------------|------------|----------|-------------|------------|------|
| 2017-07-03 | sh.600000  | 12.64 | 12.65 | 12.47 | 12.56 | 12.65    | 38778949  | 486264672  | 3          | 0.137985 | 1           | -0.711456  | 0    |
| 2017-07-04 | sh.600000  | 12.55 | 12.58 | 12.41 | 12.55 | 12.56    | 36659128  | 458434432  | 3          | 0.130442 | 1           | -0.07962   | 0    |
| 2017-07-05 | sh.600000  | 12.5  | 12.65 | 12.47 | 12.62 | 12.55    | 26470507  | 332542464  | 3          | 0.094188 | 1           | 0.557767   | 0    |
| 2017-07-06 | sh.600000  | 12.62 | 12.72 | 12.51 | 12.66 | 12.62    | 37414241  | 471582096  | 3          | 0.133129 | 1           | 0.316957   | 0    |
| 2017-07-07 | sh.600000  | 12.62 | 12.69 | 12.55 | 12.6  | 12.66    | 24667294  | 311101536  | 3          | 0.087772 | 1           | -0.473929  | 0    |

返回数据说明

| 参数名称     | 参数描述                     | 算法说明                                                                 |
|--------------|------------------------------|--------------------------------------------------------------------------|
| date         | 交易所行情日期               |                                              |
| code         | 证券代码                     |                   |
| open         | 开盘价                       |                                           |
| high         | 最高价                       |                                                 |
| low          | 最低价                       |                                              |
| close        | 收盘价                       |                                           |
| preclose     | 前收盘价                     | 见表格下方详细说明                                |
| volume       | 成交量（累计，单位：股）     |                                                    |
| amount       | 成交额（单位：人民币元）     |                                             |
| adjustflag   | 复权状态（1：后复权，2：前复权，3：不复权）|                           |
| turn         | 换手率                       | [指定交易日的成交量(股)/指定交易日的股票的流通股总数(股)]*100%                        |
| tradestatus  | 交易状态（1：正常交易，0：停牌）  |                                          |
| pctChg       | 涨跌幅（百分比）             | 日涨跌幅=[(指定交易日的收盘价-指定交易日前收盘价)/指定交易日前收盘价]*100%                   |
| peTTM        | 滚动市盈率                   | (指定交易日的股票收盘价/指定交易日的每股盈余TTM)=(指定交易日的股票收盘价*截至当日公司总股本)/归属母公司股东净利润TTM                 |
| pbMRQ        | 市净率                       | (指定交易日的股票收盘价/指定交易日的每股净资产)=总市值/(最近披露的归属母公司股东的权益-其他权益工具)                  |
| psTTM        | 滚动市销率                   | (指定交易日的股票收盘价/指定交易日的每股销售额)=(指定交易日的股票收盘价*截至当日公司总股本)/营业总收入TTM                             |
| pcfNcfTTM    | 滚动市现率                   | (指定交易日的股票收盘价/指定交易日的每股现金流TTM)=(指定交易日的股票收盘价*截至当日公司总股本)/现金以及现金等价物净增加额TTM              |
| isST         | 是否ST股,1：是，0：否                    |                                                 |


**注意“前收盘价”说明**：

证券在指定交易日行情数据的前收盘价，当日发生除权除息时，“前收盘价”不是前一天的实际收盘价，而是根据股权登记日收盘价与分红现金的数量、配送股的数里和配股价的高低等结合起来算出来的价格。

具体计算方法如下:

1、计算除息价:

除息价=股息登记日的收盘价-每股所分红利现金额

2、计算除权价:

送红股后的除权价=股权登记日的收盘价/(1+每股送红股数)

配股后的除权价=(股权登记日的收盘价+配股价\*每股配股数)/(1+每股配股数)

3、计算除权除息价

除权除息价=(股权登记日的收盘价-每股所分红利现金额+配股价\*每股配股数)/(1+每股送红股数+每股配股数)

“前收盘价”由交易所计算并公布。首发日的“前收盘价”等于“首发价格”。

##### <a id="历史行情指标参数"></a>历史行情指标参数

日线指标参数（包含停牌证券）

| 参数名称 | 参数描述 | 说明 |
|------------|------------|-------|
| date | 交易所行情日期 | 格式：YYYY-MM-DD |
| code | 证券代码 | 格式：sh.600000。sh：上海，sz：深圳 |
| open | 今开盘价格 | 精度：小数点后4位；单位：人民币元 |
| high | 最高价 | 精度：小数点后4位；单位：人民币元 |
| low | 最低价 | 精度：小数点后4位；单位：人民币元 |
| close | 今收盘价 | 精度：小数点后4位；单位：人民币元 |
| preclose | 昨日收盘价 | 精度：小数点后4位；单位：人民币元 |
| volume | 成交数量 | 单位：股 |
| amount | 成交金额 | 精度：小数点后4位；单位：人民币元 |
| adjustflag | 复权状态 | 不复权、前复权、后复权 |
| turn | 换手率 | 精度：小数点后6位；单位：% |
| tradestatus | 交易状态 | 1：正常交易 0：停牌 |
| pctChg | 涨跌幅（百分比） | 精度：小数点后6位 |
| peTTM | 滚动市盈率 | 精度：小数点后6位 |
| psTTM | 滚动市销率 | 精度：小数点后6位 |
| pcfNcfTTM | 滚动市现率 | 精度：小数点后6位 |
| pbMRQ | 市净率 | 精度：小数点后6位 |
| isST | 是否ST | 1是，0否 |

周、月线指标参数

| 参数名称 | 参数描述 | 说明 | 算法说明 |
|------------|------------|-------|-------|
| date | 交易所行情日期 | 格式：YYYY-MM-DD |  |
| code | 证券代码 | 格式：sh.600000。sh：上海，sz：深圳 |  |
| open | 开盘价格 | 精度：小数点后4位；单位：人民币元 |  |
| high | 最高价 | 精度：小数点后4位；单位：人民币元 |  |
| low | 最低价 | 精度：小数点后4位；单位：人民币元 |  |
| close | 收盘价 | 精度：小数点后4位；单位：人民币元 |  |
| volume | 成交数量 | 单位：股 |  |
| amount | 成交金额 | 精度：小数点后4位；单位：人民币元 |  |
| adjustflag | 复权状态 | 不复权、前复权、后复权 |  |
| turn | 换手率 | 精度：小数点后6位；单位：% |  |
| pctChg | 涨跌幅（百分比） | 精度：小数点后6位 | 涨跌幅=[(区间最后交易日收盘价-区间首个交易日前收盘价)/区间首个交易日前收盘价]\*100% |

5、15、30、60分钟线指标参数(不包含指数)

| 参数名称 | 参数描述 | 说明 |
|------------|------------|-------|
| date | 交易所行情日期 | 格式：YYYY-MM-DD |
| time | 交易所行情时间 | 格式：YYYYMMDDHHMMSSsss |
| code | 证券代码 | 格式：sh.600000。sh：上海，sz：深圳 |
| open | 开盘价格 | 精度：小数点后4位；单位：人民币元 |
| high | 最高价 | 精度：小数点后4位；单位：人民币元 |
| low | 最低价 | 精度：小数点后4位；单位：人民币元 |
| close | 收盘价 | 精度：小数点后4位；单位：人民币元 |
| volume | 成交数量 | 单位：股； 时间范围内的累计成交数量 |
| amount | 成交金额 | 精度：小数点后4位；单位：人民币元； 时间范围内的累计成交金额 |
| adjustflag | 复权状态 | 不复权、前复权、后复权 |



#### <a id="查询除权除息信息"></a>查询除权除息信息

##### <a id="query_dividend_data"></a>除权除息信息：query\_dividend\_data()

通过API接口获取除权除息信息数据（预披露、预案、正式都已通过）。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_Dividend_data.xlsx)

```

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 查询除权除息信息####
# 查询2015年除权除息信息
rs_list = []
rs_dividend_2015 = bs.query_dividend_data(code="sh.600000", year="2015", yearType="report")
while (rs_dividend_2015.error_code == '0') & rs_dividend_2015.next():
    rs_list.append(rs_dividend_2015.get_row_data())

# 查询2016年除权除息信息
rs_dividend_2016 = bs.query_dividend_data(code="sh.600000", year="2016", yearType="report")
while (rs_dividend_2016.error_code == '0') & rs_dividend_2016.next():
    rs_list.append(rs_dividend_2016.get_row_data())

# 查询2017年除权除息信息
rs_dividend_2017 = bs.query_dividend_data(code="sh.600000", year="2017", yearType="report")
while (rs_dividend_2017.error_code == '0') & rs_dividend_2017.next():
    rs_list.append(rs_dividend_2017.get_row_data())

result_dividend = pd.DataFrame(rs_list, columns=rs_dividend_2017.fields)
# 打印输出
print(result_dividend)

#### 结果集输出到csv文件 ####   
result_dividend.to_csv("D:\\history_Dividend_data.csv", encoding="gbk",index=False)

#### 登出系统 ####
bs.logout()


```



参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：年份，如：2017。此参数不可为空；
* yearType：年份类别，默认为"report":预案公告年份，可选项"operate":除权除息年份。此参数不可为空。



返回示例数据

| code | dividPreNoticeDate | dividAgmPumDate | dividPlanAnnounceDate | dividPlanDate | dividRegistDate | dividOperateDate | dividPayDate |
|------------|------------|-------|-------|-------|-------|----------|-----------|
| sh.600000 |  | 2015-05-16 | 2015-03-19 | 2015-06-16 | 2015-06-19 | 2015-06-23 | 2015-06-23 |
| sh.600000 |  | 2016-04-29 | 2016-04-07 | 2016-06-16 | 2016-06-22 | 2016-06-23 | 2016-06-23 |
| sh.600000 |  | 2017-04-26 | 2017-04-01 | 2017-05-19 | 2017-05-24 | 2017-05-25 | 2017-05-25 |

返回示例数据

| dividStockMarketDate | dividCashPsBeforeTax | dividCashPsAfterTax | dividStocksPs | dividCashStock | dividReserveToStockPs |
|------------|------------|-------|------------|------------|-------|
|  | 0.757 | 0.6813或0.71915 | 0.000000 | 10派7.57元（含税，扣税后6.813或7.1915元） |  |
| 2016-06-24 | 0.515 | 0.4635或0.515 | 0.000000 | 10转1派5.15元（含税，扣税后4.635或5.15元） | 0.100000 |
| 2017-05-26 | 0.2 | 0.18或0.2 | 0.000000 | 10转3派2元（含税，扣税后1.8或2元） | 0.300000 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| dividPreNoticeDate | 预批露公告日 |  |
| dividAgmPumDate | 股东大会公告日期 |  |
| dividPlanAnnounceDate | 预案公告日 |  |
| dividPlanDate | 分红实施公告日 |  |
| dividRegistDate | 股权登记告日 |  |
| dividOperateDate | 除权除息日期 |  |
| dividPayDate | 派息日 |  |
| dividStockMarketDate | 红股上市交易日 |  |
| dividCashPsBeforeTax | 每股股利税前 | 派息比例分子(税前)/派息比例分母 |
| dividCashPsAfterTax | 每股股利税后 | 派息比例分子(税后)/派息比例分母 |
| dividStocksPs | 每股红股 |  |
| dividCashStock | 分红送转 | 每股派息数(税前)+每股送股数+每股转增股本数 |
| dividReserveToStockPs | 每股转增资本 |  |

#### <a id="查询复权因子信息"></a>查询复权因子信息

##### <a id="query_adjust_factor"></a>复权因子：query\_adjust\_factor()

通过API接口获取复权因子信息数据。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/adjust_factor_data.xlsx)

BaoStock提供的是**涨跌幅复权算法**复权因子，具体介绍见： [媒体文件:BaoStock复权因子简介.pdf](https://baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf "BaoStock复权因子简介.pdf")。

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 查询2015至2017年复权因子
rs_list = []
rs_factor = bs.query_adjust_factor(code="sh.600000", start_date="2015-01-01", end_date="2017-12-31")
while (rs_factor.error_code == '0') & rs_factor.next():
    rs_list.append(rs_factor.get_row_data())
result_factor = pd.DataFrame(rs_list, columns=rs_factor.fields)
# 打印输出
print(result_factor)

# 结果集输出到csv文件
result_factor.to_csv("D:\\adjust_factor_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()

```



参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* start\_date：开始日期，为空时默认为2015-01-01，包含此日期；
* end\_date：结束日期，为空时默认当前日期，包含此日期。

返回示例数据

| code | dividOperateDate | foreAdjustFactor | backAdjustFactor | adjustFactor |
|------------|------------|-------|-------|-------|
| sh.600000 | 2015-06-23 | 0.663792 | 6.295967 | 6.295967 |
| sh.600000 | 2016-06-23 | 0.751598 | 7.128788 | 7.128788 |
| sh.600000 | 2017-05-25 | 0.989551 | 9.385732 | 9.385732 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| dividOperateDate | 除权除息日期 |  |
| foreAdjustFactor | 向前复权因子 | 除权除息日前一个交易日的收盘价/除权除息日最近的一个交易日的前收盘价 |
| backAdjustFactor | 向后复权因子 | 除权除息日最近的一个交易日的前收盘价/除权除息日前一个交易日的收盘价 |
| adjustFactor | 本次复权因子 |  |

#### <a id="查询季频财务数据信息"></a>查询季频财务数据信息

##### <a id="query_profit_data"></a>季频盈利能力：query\_profit\_data()

方法说明：通过API接口获取季频盈利能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。

返回类型：pandas的DataFrame类型。

使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 查询季频估值指标盈利能力
profit_list = []
rs_profit = bs.query_profit_data(code="sh.600000", year=2017, quarter=2)
while (rs_profit.error_code == '0') & rs_profit.next():
    profit_list.append(rs_profit.get_row_data())
result_profit = pd.DataFrame(profit_list, columns=rs_profit.fields)
# 打印输出
print(result_profit)
# 结果集输出到csv文件
result_profit.to_csv("D:\\profit_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()

```



参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：统计年份，为空时默认当前年；
* quarter：统计季度，可为空，默认当前季度。不为空时只有4个取值：1，2，3，4。

返回示例数据

| code | pubDate | statDate | roeAvg | npMargin | gpMargin | netProfit | epsTTM | MBRevenue | totalShare | liqaShare |
|------------|------------|-------|------------|------------|-------|------------|-------|------------|------------|-------|
| sh.600000 | 2017-08-30 | 2017-06-30 | 0.074617 | 0.342179 |  | 28522000000.000000 | 1.939029 | 83354000000.000000 | 28103763899.00 | 28103763899.00 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| pubDate | 公司发布财报的日期 |  |
| statDate | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30 |  |
| roeAvg | 净资产收益率(平均)(%) | 归属母公司股东净利润/[(期初归属母公司股东的权益+期末归属母公司股东的权益)/2]\*100% |
| npMargin | 销售净利率(%) | 净利润/营业收入\*100% |
| gpMargin | 销售毛利率(%) | 毛利/营业收入\*100%=(营业收入-营业成本)/营业收入\*100% |
| netProfit | 净利润(元) |  |
| epsTTM | 每股收益 | 归属母公司股东的净利润TTM/最新总股本 |
| MBRevenue | 主营营业收入(元) |  |
| totalShare | 总股本 |  |
| liqaShare | 流通股本 |  |



##### <a id="query_operation_data"></a>季频营运能力：query\_operation\_data()

方法说明：通过API接口获取季频营运能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。

返回类型：pandas的DataFrame类型。

使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 营运能力
operation_list = []
rs_operation = bs.query_operation_data(code="sh.600000", year=2017, quarter=2)
while (rs_operation.error_code == '0') & rs_operation.next():
    operation_list.append(rs_operation.get_row_data())
result_operation = pd.DataFrame(operation_list, columns=rs_operation.fields)
# 打印输出
print(result_operation)
# 结果集输出到csv文件
result_operation.to_csv("D:\\operation_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()

```



参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：统计年份，为空时默认当前年；
* quarter：统计季度，为空时默认当前季度。不为空时只有4个取值：1，2，3，4。

返回示例数据

| code | pubDate | statDate | NRTurnRatio | NRTurnDays | INVTurnRatio | INVTurnDays | CATurnRatio | AssetTurnRatio |
|------------|------------|-------|------------|------------|-------|------------|------------|-------|
| sh.600000 | 2017-08-30 | 2017-06-30 |  |  |  |  |  | 0.014161 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| pubDate | 公司发布财报的日期 |  |
| statDate | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30 |  |
| NRTurnRatio | 应收账款周转率(次) | 营业收入/[(期初应收票据及应收账款净额+期末应收票据及应收账款净额)/2] |
| NRTurnDays | 应收账款周转天数(天) | 季报天数/应收账款周转率(一季报：90天，中报：180天，三季报：270天，年报：360天) |
| INVTurnRatio | 存货周转率(次) | 营业成本/[(期初存货净额+期末存货净额)/2] |
| INVTurnDays | 存货周转天数(天) | 季报天数/存货周转率(一季报：90天，中报：180天，三季报：270天，年报：360天) |
| CATurnRatio | 流动资产周转率(次) | 营业总收入/[(期初流动资产+期末流动资产)/2] |
| AssetTurnRatio | 总资产周转率 | 营业总收入/[(期初资产总额+期末资产总额)/2] |




##### <a id="query_growth_data"></a>季频成长能力：query\_growth\_data()

方法说明：通过API接口获取季频成长能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 成长能力
growth_list = []
rs_growth = bs.query_growth_data(code="sh.600000", year=2017, quarter=2)
while (rs_growth.error_code == '0') & rs_growth.next():
    growth_list.append(rs_growth.get_row_data())
result_growth = pd.DataFrame(growth_list, columns=rs_growth.fields)
# 打印输出
print(result_growth)
# 结果集输出到csv文件
result_growth.to_csv("D:\\growth_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()


```




参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：统计年份，为空时默认当前年；
* quarter：统计季度，为空时默认当前季度。不为空时只有4个取值：1，2，3，4。

返回示例数据

| code | pubDate | statDate | YOYEquity | YOYAsset | YOYNI | YOYEPSBasic | YOYPNI |
|------------|------------|-------|------------|------------|-------|------------|-------|
| sh.600000 | 2017-08-30 | 2017-06-30 | 0.120243 | 0.101298 | 0.054808 | 0.021053 | 0.052111 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| pubDate | 公司发布财报的日期 |  |
| statDate | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30 |  |
| YOYEquity | 净资产同比增长率 | (本期净资产-上年同期净资产)/上年同期净资产的绝对值\*100% |
| YOYAsset | 总资产同比增长率 | (本期总资产-上年同期总资产)/上年同期总资产的绝对值\*100% |
| YOYNI | 净利润同比增长率 | (本期净利润-上年同期净利润)/上年同期净利润的绝对值\*100% |
| YOYEPSBasic | 基本每股收益同比增长率 | (本期基本每股收益-上年同期基本每股收益)/上年同期基本每股收益的绝对值\*100% |
| YOYPNI | 归属母公司股东净利润同比增长率 | (本期归属母公司股东净利润-上年同期归属母公司股东净利润)/上年同期归属母公司股东净利润的绝对值\*100% |




##### <a id="query_balance_data"></a>季频偿债能力：query\_balance\_data()

方法说明：通过API接口获取季频偿债能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 偿债能力
balance_list = []
rs_balance = bs.query_balance_data(code="sh.600000", year=2017, quarter=2)
while (rs_balance.error_code == '0') & rs_balance.next():
    balance_list.append(rs_balance.get_row_data())
result_balance = pd.DataFrame(balance_list, columns=rs_balance.fields)
# 打印输出
print(result_balance)
# 结果集输出到csv文件
result_balance.to_csv("D:\\balance_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()

```




参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：统计年份，为空时默认当前年；
* quarter：统计季度，为空时默认当前季度。不为空时只有4个取值：1，2，3，4。

返回示例数据

| code | pubDate | statDate | currentRatio | quickRatio | cashRatio | YOYLiability | liabilityToAsset | assetToEquity |
|------------|------------|-------|------------|------------|-------|------------|------------|-------|
| sh.600000 | 2017-08-30 | 2017-06-30 |  |  |  | 0.100020 | 0.933703 | 15.083598 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| pubDate | 公司发布财报的日期 |  |
| statDate | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30 |  |
| currentRatio | 流动比率 | 流动资产/流动负债 |
| quickRatio | 速动比率 | (流动资产-存货净额)/流动负债 |
| cashRatio | 现金比率 | (货币资金+交易性金融资产)/流动负债 |
| YOYLiability | 总负债同比增长率 | (本期总负债-上年同期总负债)/上年同期中负债的绝对值\*100% |
| liabilityToAsset | 资产负债率 | 负债总额/资产总额 |
| assetToEquity | 权益乘数 | 资产总额/股东权益总额=1/(1-资产负债率) |




##### <a id="query_cash_flow_data"></a>季频现金流量：query\_cash\_flow\_data()

方法说明：通过API接口获取季频现金流量信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 季频现金流量
cash_flow_list = []
rs_cash_flow = bs.query_cash_flow_data(code="sh.600000", year=2017, quarter=2)
while (rs_cash_flow.error_code == '0') & rs_cash_flow.next():
    cash_flow_list.append(rs_cash_flow.get_row_data())
result_cash_flow = pd.DataFrame(cash_flow_list, columns=rs_cash_flow.fields)
# 打印输出
print(result_cash_flow)
# 结果集输出到csv文件
result_cash_flow.to_csv("D:\\cash_flow_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()

```




参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：统计年份，为空时默认当前年；
* quarter：统计季度，为空时默认当前季度。不为空时只有4个取值：1，2，3，4。

返回示例数据

| code | pubDate | statDate | CAToAsset | NCAToAsset | tangibleAssetToAsset | ebitToInterest | CFOToOR | CFOToNP | CFOToGr |
|------------|------------|-------|------------|------------|-------|------------|------------|-------|-------|
| sh.600000 | 2017-08-30 | 2017-06-30 |  |  |  |  | —3.071550 | —8.976439 | —3.071550 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| pubDate | 公司发布财报的日期 |  |
| statDate | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30 |  |
| CAToAsset | 流动资产除以总资产 |  |
| NCAToAsset | 非流动资产除以总资产 |  |
| tangibleAssetToAsset | 有形资产除以总资产 |  |
| ebitToInterest | 已获利息倍数 | 息税前利润/利息费用 |
| CFOToOR | 经营活动产生的现金流量净额除以营业收入 |  |
| CFOToNP | 经营性现金净流量除以净利润 |  |
| CFOToGr | 经营性现金净流量除以营业总收入 |  |




##### <a id="query_dupont_data"></a>季频杜邦指数：query\_dupont\_data()

方法说明：通过API接口获取季频杜邦指数信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 查询杜邦指数
dupont_list = []
rs_dupont = bs.query_dupont_data(code="sh.600000", year=2017, quarter=2)
while (rs_dupont.error_code == '0') & rs_dupont.next():
    dupont_list.append(rs_dupont.get_row_data())
result_dupont = pd.DataFrame(dupont_list, columns=rs_dupont.fields)
# 打印输出
print(result_dupont)
# 结果集输出到csv文件
result_dupont.to_csv("D:\\dupont_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()

```




参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* year：统计年份，为空时默认当前年；
* quarter：统计季度，为空时默认当前季度。不为空时只有4个取值：1，2，3，4。

返回示例数据

| code | pubDate | statDate | dupontROE | dupontAssetStoEquity | dupontAssetTurn | dupontPnitoni |
|------------|------------|-------|------------|------------|-------|------------|
| sh.600000 | 2017-08-30 | 2017-06-30 | 0.074617 | 15.594453 | 0.014161 | 0.987483 |

返回示例数据

| dupontNitogr | dupontTaxBurden | dupontIntburden | dupontEbittogr |
|------------|------------|-------|-------|
| 0.342179 | 0.776088 |  |  |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| code | 证券代码 |  |
| pubDate | 公司发布财报的日期 |  |
| statDate | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30 |  |
| dupontROE | 净资产收益率 | 归属母公司股东净利润/[(期初归属母公司股东的权益+期末归属母公司股东的权益)/2]\*100% |
| dupontAssetStoEquity | 权益乘数，反映企业财务杠杆效应强弱和财务风险 | 平均总资产/平均归属于母公司的股东权益 |
| dupontAssetTurn | 总资产周转率，反映企业资产管理效率的指标 | 营业总收入/[(期初资产总额+期末资产总额)/2] |
| dupontPnitoni | 归属母公司股东的净利润/净利润，反映母公司控股子公司百分比。如果企业追加投资，扩大持股比例，则本指标会增加。 |  |
| dupontNitogr | 净利润/营业总收入，反映企业销售获利率 |  |
| dupontTaxBurden | 净利润/利润总额，反映企业税负水平，该比值高则税负较低。净利润/利润总额=1-所得税/利润总额 |  |
| dupontIntburden | 利润总额/息税前利润，反映企业利息负担，该比值高则税负较低。利润总额/息税前利润=1-利息费用/息税前利润 |
| dupontEbittogr | 息税前利润/营业总收入，反映企业经营利润率，是企业经营获得的可供全体投资人（股东和债权人）分配的盈利占企业全部营收收入的百分比 |  |




#### <a id="查询季频公司报告信息"></a>查询季频公司报告信息

##### <a id="query_performance_express_report"></a>季频公司业绩快报：query\_performance\_express\_report()

方法说明：通过API接口获取季频公司业绩快报信息，可以通过参数设置获取起止年份数据，提供2006年至今数据。除几种特殊情况外，交易所未要求必须发布。

返回类型：pandas的DataFrame类型。

使用示例

```

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取公司业绩快报 ####
rs = bs.query_performance_express_report("sh.600000", start_date="2015-01-01", end_date="2017-12-31")
print('query_performance_express_report respond error_code:'+rs.error_code)
print('query_performance_express_report respond  error_msg:'+rs.error_msg)

result_list = []
while (rs.error_code == '0') & rs.next():
    result_list.append(rs.get_row_data())
    # 获取一条记录，将记录合并在一起
result = pd.DataFrame(result_list, columns=rs.fields)
#### 结果集输出到csv文件 ####
result.to_csv("D:\\performance_express_report.csv", encoding="gbk", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```




参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* start\_date：开始日期，发布日期或更新日期在这个范围内；
* end\_date：结束日期，发布日期或更新日期在这个范围内。

返回示例数据

| code | performanceExpPubDate | performanceExpStatDate | performanceExpUpdateDate | performanceExpressTotalAsset | performanceExpressNetAsset |
|------------|------------|-------|------------|------------|-------|
| sh.600000 | 2015-01-06 | 2014-12-31 | 2015-01-06 | 4195602000000.000000 | 260011000000.000000 |
| sh.600000 | 2016-01-05 | 2015-12-31 | 2016-01-05 | 5043060000000.000000 | 285245000000.000000 |
| sh.600000 | 2017-01-04 | 2016-12-31 | 2017-01-04 | 5857263000000.000000 | 338027000000.000000 |

返回示例数据

| performanceExpressEPSChgPct | performanceExpressROEWa | performanceExpressEPSDiluted | performanceExpressGRYOY | performanceExpressOPYOY |
|------------|------------|-------|------------|------------|
| 0.326910 | 21.020000 | 2.520000 | 0.228390 | 0.153803 |
| 0.191493 | 18.820000 | 2.660000 | 0.192395 | 0.069764 |
| 0.115412 | 16.350000 | 2.400000 | 0.097234 | 0.054384 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| code | 证券代码 |
| performanceExpPubDate | 业绩快报披露日 |
| performanceExpStatDate | 业绩快报统计日期 |
| performanceExpUpdateDate | 业绩快报披露日(最新) |
| performanceExpressTotalAsset | 业绩快报总资产 |
| performanceExpressNetAsset | 业绩快报净资产 |
| performanceExpressEPSChgPct | 业绩每股收益增长率 |
| performanceExpressROEWa | 业绩快报净资产收益率ROE-加权 |
| performanceExpressEPSDiluted | 业绩快报每股收益EPS-摊薄 |
| performanceExpressGRYOY | 业绩快报营业总收入同比 |
| performanceExpressOPYOY | 业绩快报营业利润同比 |




##### <a id="query_forecast_report"></a>季频公司业绩预告：query\_forecast\_report()

方法说明：通过API接口获取季频公司业绩预告信息，可以通过参数设置获取起止年份数据，提供2003年至今数据。除几种特殊情况外，交易所未要求必须发布。

返回类型：pandas的DataFrame类型。

使用示例

```

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取公司业绩预告 ####
rs_forecast = bs.query_forecast_report("sh.600000", start_date="2010-01-01", end_date="2017-12-31")
print('query_forecast_reprot respond error_code:'+rs_forecast.error_code)
print('query_forecast_reprot respond  error_msg:'+rs_forecast.error_msg)
rs_forecast_list = []
while (rs_forecast.error_code == '0') & rs_forecast.next():
    # 分页查询，将每页信息合并在一起
    rs_forecast_list.append(rs_forecast.get_row_data())
result_forecast = pd.DataFrame(rs_forecast_list, columns=rs_forecast.fields)
#### 结果集输出到csv文件 ####
result_forecast.to_csv("D:\\forecast_report.csv", encoding="gbk", index=False)
print(result_forecast)

#### 登出系统 ####
bs.logout()

```




参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* start\_date：开始日期，发布日期或更新日期在这个范围内；
* end\_date：结束日期，发布日期或更新日期在这个范围内。

返回示例数据

| code | profitForcastExpPubDate | profitForcastExpStatDate | profitForcastType | profitForcastAbstract |
|------------|------------|-------|------------|-------|
| sh.600000 | 2010-01-05 | 2009-12-31 | 略增 | 预计2009年归属于上市公司股东净利润1319500万元，同比增长5.43%。 |
| sh.600000 | 2011-01-05 | 2010-12-31 | 略增 | 预计公司2010年年度归属于上市公司股东净利润为190.76亿元，较上年同期增长44.33％。 |
| sh.600000 | 2012-01-05 | 2011-12-31 | 略增 | 预计2011年1月1日至2011年12月31日，归属于上市公司股东的净利润：盈利272.36亿元，与上年同期相比增加了42.02%。 |

返回示例数据

| profitForcastChgPctUp | profitForcastChgPctDwn |
|------------|------------|
| 5.430000 | 0.000000 |
| 44.330000 | 44.330000 |
| 42.020000 | 42.020000 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| code | 证券代码 |
| profitForcastExpPubDate | 业绩预告发布日期 |
| profitForcastExpStatDate | 业绩预告统计日期 |
| profitForcastType | 业绩预告类型 |
| profitForcastAbstract | 业绩预告摘要 |
| profitForcastChgPctUp | 预告归属于母公司的净利润增长上限(%) |
| profitForcastChgPctDwn | 预告归属于母公司的净利润增长下限(%) |

#### <a id="证券基本资料"></a>证券基本资料

##### <a id="query_stock_basic"></a>证券基本资料：query\_stock\_basic()

方法说明：通过API接口获取证券基本资料，可以通过参数设置获取对应证券代码、证券名称的数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取证券基本资料
rs = bs.query_stock_basic(code="sh.600000")
# rs = bs.query_stock_basic(code_name="浦发银行")  # 支持模糊查询
print('query_stock_basic respond error_code:'+rs.error_code)
print('query_stock_basic respond  error_msg:'+rs.error_msg)

# 打印结果集
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/stock_basic.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()


```




参数含义：

* code：A股股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。可以为空；
* code\_name：股票名称，支持模糊查询，可以为空。
* 当参数为空时，输出全部股票的基本信息。

返回示例数据

| code | code\_name | ipoDate | outDate | type | status |
|------------|------------|-------|------------|------------|-------|
| sh.600000 | 浦发银行 | 1999-11-10 |  | 1 | 1 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| code | 证券代码 |
| code\_name | 证券名称 |
| ipoDate | 上市日期 |
| outDate | 退市日期 |
| type | 证券类型，其中1：股票，2：指数，3：其它，4：可转债，5：ETF |
| status | 上市状态，其中1：上市，0：退市 |




#### <a id="获取证券元信息"></a>获取证券元信息

##### <a id="query_trade_dates"></a>交易日查询：query\_trade\_dates()

方法说明：通过API接口获取股票交易日信息，可以通过参数设置获取起止年份数据，提供上交所1990-今年数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取交易日信息 ####
rs = bs.query_trade_dates(start_date="2017-01-01", end_date="2017-06-30")
print('query_trade_dates respond error_code:'+rs.error_code)
print('query_trade_dates respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

#### 结果集输出到csv文件 ####   
result.to_csv("D:\\trade_datas.csv", encoding="gbk", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```




参数含义：

* start\_date：开始日期，为空时默认为2015-01-01。
* end\_date：结束日期，为空时默认为当前日期。

返回示例数据

| calendar\_date | is\_trading\_day |
|------------|------------|
| 2017-01-01 | 0 |
| 2017-01-02 | 0 |
| 2017-01-03 | 1 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| calendar\_date | 日期 |
| is\_trading\_day | 是否交易日(0:非交易日;1:交易日) |




##### <a id="query_all_stock"></a>证券代码查询：query\_all\_stock()

方法说明：获取指定交易日期所有股票列表。通过API接口获取证券代码及股票交易状态信息，与日K线数据同时更新。可以通过参数‘某交易日’获取数据（包括：A股、指数），数据范围同接口query\_history\_k\_data\_plus()。

返回类型：pandas的DataFrame类型。

更新时间：与日K线同时更新。

使用示例

```

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取证券信息 ####
rs = bs.query_all_stock(day="2017-06-30")
print('query_all_stock respond error_code:'+rs.error_code)
print('query_all_stock respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

#### 结果集输出到csv文件 ####   
result.to_csv("D:\\all_stock.csv", encoding="gbk", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```




参数含义：

* day：需要查询的交易日期，为空时默认当前日期。

返回示例数据

| code | tradeStatus | code\_name |
|------------|------------|-------|
| sh.000001 | 1 | 上证综合指数 |
| sh.000002 | 1 | 上证A股指数 |
| sh.000003 | 1 | 上证B股指数 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| code | 证券代码 |
| tradeStatus | 交易状态(1：正常交易 0：停牌） |
| code\_name | 证券名称 |



#### <a id="宏观经济数据"></a>宏观经济数据

##### <a id="query_deposit_rate_data"></a>存款利率：query\_deposit\_rate\_data()

方法说明：通过API接口获取存款利率，可以通过参数设置获取对应起止日期的数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取存款利率
rs = bs.query_deposit_rate_data(start_date="2015-01-01", end_date="2015-12-31")
print('query_deposit_rate_data respond error_code:'+rs.error_code)
print('query_deposit_rate_data respond  error_msg:'+rs.error_msg)

# 打印结果集
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/deposit_rate.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()

```




参数含义：

* start\_date：开始日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空；
* end\_date：结束日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空。

返回示例数据

| pubDate | demandDepositRate | fixedDepositRate3Month | fixedDepositRate6Month | fixedDepositRate1Year | fixedDepositRate2Year | fixedDepositRate3Year |
|------------|------------|-------|------------|------------|-------|------------|
| 2015-03-01 | 0.350000 | 2.100000 | 2.300000 | 2.500000 | 3.100000 | 3.750000 |
| 2015-05-11 | 0.350000 | 1.850000 | 2.050000 | 2.250000 | 2.850000 | 3.500000 |

返回示例数据

| fixedDepositRate5Year | installmentFixedDepositRate1Year | installmentFixedDepositRate3Year | installmentFixedDepositRate5Year |
|------------|------------|-------|------------|
|  | 2.100000 | 2.300000 |  |
|  | 1.850000 | 2.050000 |  |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| pubDate | 发布日期 |
| demandDepositRate | 活期存款(不定期) |
| fixedDepositRate3Month | 定期存款(三个月) |
| fixedDepositRate6Month | 定期存款(半年) |
| fixedDepositRate1Year | 定期存款整存整取(一年) |
| fixedDepositRate2Year | 定期存款整存整取(二年) |
| fixedDepositRate3Year | 定期存款整存整取(三年) |
| fixedDepositRate5Year | 定期存款整存整取(五年) |
| installmentFixedDepositRate1Year | 零存整取、整存零取、存本取息定期存款(一年) |
| installmentFixedDepositRate3Year | 零存整取、整存零取、存本取息定期存款(三年) |
| installmentFixedDepositRate5Year | 零存整取、整存零取、存本取息定期存款(五年) |




##### <a id="query_loan_rate_data"></a>贷款利率：query\_loan\_rate\_data()

方法说明：通过API接口获取贷款利率，可以通过参数设置获取对应起止日期的数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取贷款利率
rs = bs.query_loan_rate_data(start_date="2010-01-01", end_date="2015-12-31")
print('query_loan_rate_data respond error_code:'+rs.error_code)
print('query_loan_rate_data respond  error_msg:'+rs.error_msg)

# 打印结果集
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/loan_rate.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()

```




参数含义：

* start\_date：开始日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空；
* end\_date：结束日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空。

返回示例数据

| pubDate | loanRate6Month | loanRate6MonthTo1Year | loanRate1YearTo3Year | loanRate3YearTo5Year |
|------------|------------|-------|------------|------------|
| 2010-10-20 | 5.100000 | 5.560000 | 5.600000 | 5.960000 |
| 2010-12-26 | 5.350000 | 5.810000 | 5.850000 | 6.220000 |

返回示例数据

| loanRateAbove5Year | mortgateRateBelow5Year | mortgateRateAbove5Year |
|------------|------------|-------|
| 6.140000 | 3.500000 | 4.050000 |
| 6.400000 | 3.750000 | 4.300000 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| pubDate | 发布日期 |
| loanRate6Month | 6个月贷款利率 |
| loanRate6MonthTo1Year | 6个月至1年贷款利率 |
| loanRate1YearTo3Year | 1年至3年贷款利率 |
| loanRate3YearTo5Year | 3年至5年贷款利率 |
| loanRateAbove5Year | 5年以上贷款利率 |
| mortgateRateBelow5Year | 5年以下住房公积金贷款利率 |
| mortgateRateAbove5Year | 5年以上住房公积金贷款利率 |




##### <a id="query_required_reserve_ratio_data"></a>存款准备金率：query\_required\_reserve\_ratio\_data()

方法说明：通过API接口获取存款准备金率，可以通过参数设置获取对应起止日期的数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取存款准备金率
rs = bs.query_required_reserve_ratio_data(start_date="2010-01-01", end_date="2015-12-31")
print('query_required_reserve_ratio_data respond error_code:'+rs.error_code)
print('query_required_reserve_ratio_data respond  error_msg:'+rs.error_msg)

# 打印结果集
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/required_reserve_ratio.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()

```




参数含义：

* start\_date：开始日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空；
* end\_date：结束日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空；
* yearType:年份类别，默认为0，查询公告日期；1查询生效日期。

返回示例数据

| pubDate | effectiveDate | bigInstitutionsRatioPre | bigInstitutionsRatioAfter |
|------------|------------|-------|------------|
| 2010-01-12 | 2010-01-18 | 15.5 | 16.0 |
| 2010-02-12 | 2010-02-25 | 16.0 | 16.5 |

返回示例数据

| mediumInstitutionsRatioPre | mediumInstitutionsRatioAfter |
|------------|------------|
| 13.5 | 14.0 |
| 14.0 | 14.5 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| pubDate | 公告日期 |
| effectiveDate | 生效日期 |
| bigInstitutionsRatioPre | 人民币存款准备金率：大型存款类金融机构 调整前 |
| bigInstitutionsRatioAfter | 人民币存款准备金率：大型存款类金融机构 调整后 |
| mediumInstitutionsRatioPre | 人民币存款准备金率：中小型存款类金融机构 调整前 |
| mediumInstitutionsRatioAfter | 人民币存款准备金率：中小型存款类金融机构 调整后 |




##### <a id="query_money_supply_data_month"></a>货币供应量：query\_money\_supply\_data\_month()

方法说明：通过API接口获取货币供应量，可以通过参数设置获取对应起止日期的数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取货币供应量
rs = bs.query_money_supply_data_month(start_date="2010-01", end_date="2015-12")
print('query_money_supply_data_month respond error_code:'+rs.error_code)
print('query_money_supply_data_month respond  error_msg:'+rs.error_msg)

# 打印结果集
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/money_supply_data_month.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()

```




参数含义：

* start\_date：开始日期，格式XXXX-XX，发布日期在这个范围内，可以为空；
* end\_date：结束日期，格式XXXX-XX，发布日期在这个范围内，可以为空。

返回示例数据

| statYear | statMonth | m0Month | m0YOY | m0ChainRelative | m1Month | m1YOY | m1ChainRelative |
|------------|------------|-------|------------|------------|-------|------------|------------|
| 2010 | 01 | 40758.580000 | —0.790000 | 6.566809 | 229588.980000 | 38.960000 | 3.677276 |
| 2010 | 02 | 42865.790000 | 21.980000 | 5.169979 | 224286.950000 | 34.990000 | —2.309357 |

返回示例数据

| m2Month | m2YOY | m2ChainRelative |
|------------|------------|-------|
| 625609.290000 | 25.980000 | 2.521165 |
| 636072.260000 | 25.520000 | 1.672445 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| statYear | 统计年度 |
| statMonth | 统计月份 |
| m0Month | 货币供应量M0（月） |
| m0YOY | 货币供应量M0（同比） |
| m0ChainRelative | 货币供应量M0（环比） |
| m1Month | 货币供应量M1（月） |
| m1YOY | 货币供应量M1（同比） |
| m1ChainRelative | 货币供应量M1（环比） |
| m2Month | 货币供应量M2（月） |
| m2YOY | 货币供应量M2（同比） |
| m2ChainRelative | 货币供应量M2（环比） |




##### <a id="query_money_supply_data_year"></a>货币供应量(年底余额)：query\_money\_supply\_data\_year()

方法说明：通过API接口获取货币供应量(年底余额)，可以通过参数设置获取对应起止日期的数据。
返回类型：pandas的DataFrame类型。
使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取货币供应量(年底余额)
rs = bs.query_money_supply_data_year(start_date="2010", end_date="2015")
print('query_money_supply_data_year respond error_code:'+rs.error_code)
print('query_money_supply_data_year respond  error_msg:'+rs.error_msg)

# 打印结果集
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/money_supply_data_year.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()

```




参数含义：

* start\_date：开始日期，格式XXXX，发布日期在这个范围内，可以为空；
* end\_date：结束日期，格式XXXX，发布日期在这个范围内，可以为空。

返回示例数据

| statYear | m0Year | m0YearYOY | m1Year | m1YearYOY | m2Year | m2YearYOY |
|------------|------------|-------|------------|------------|-------|------------|
| 2010 | 44628.170000 | 16.700000 | 266621.540000 | 21.200000 | 725851.800000 | 19.700000 |
| 2011 | 50748.460000 | 13.760000 | 289847.700000 | 7.850000 | 851590.900000 | 13.610000 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| statYear | 统计年度 |
| m0Year | 年货币供应量M0（亿元） |
| m0YearYOY | 年货币供应量M0（同比） |
| m1Year | 年货币供应量M1（亿元） |
| m1YearYOY | 年货币供应量M1（同比） |
| m2Year | 年货币供应量M2（亿元） |
| m2YearYOY | 年货币供应量M2（同比） |



#### <a id="板块数据"></a>板块数据

##### <a id="query_stock_industry"></a>行业分类：query\_stock\_industry()

方法说明：通过API接口获取行业分类信息，更新频率：每周一更新。返回类型：pandas的DataFrame类型。 使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取行业分类数据
rs = bs.query_stock_industry()
# rs = bs.query_stock_basic(code_name="浦发银行")
print('query_stock_industry error_code:'+rs.error_code)
print('query_stock_industry respond  error_msg:'+rs.error_msg)

# 打印结果集
industry_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    industry_list.append(rs.get_row_data())
result = pd.DataFrame(industry_list, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/stock_industry.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()


```




参数含义：

* code：A股股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。可以为空；
* date：查询日期，格式XXXX-XX-XX，为空时默认最新日期。

返回示例数据

| updateDate | code | code\_name | industry | industryClassification |
|------------|------------|-------|------------|------------|
| 2018-11-26 | sh.600000 | 浦发银行 | 银行 | 申万一级行业 |
| 2018-11-26 | sh.600001 | 邯郸钢铁 |  | 申万一级行业 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| updateDate | 更新日期 |
| code | 证券代码 |
| code\_name | 证券名称 |
| industry | 所属行业 |
| industryClassification | 所属行业类别 |

##### <a id="query_sz50_stocks"></a>上证50成分股：query\_sz50\_stocks()

方法说明：通过API接口获取上证50成分股信息，更新频率：每周一更新。返回类型：pandas的DataFrame类型。 使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取上证50成分股
rs = bs.query_sz50_stocks()
print('query_sz50 error_code:'+rs.error_code)
print('query_sz50  error_msg:'+rs.error_msg)

# 打印结果集
sz50_stocks = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    sz50_stocks.append(rs.get_row_data())
result = pd.DataFrame(sz50_stocks, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/sz50_stocks.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()


```




参数含义：

* date：查询日期，格式XXXX-XX-XX，为空时默认最新日期。

返回示例数据

| updateDate | code | code\_name |
|------------|------------|-------|
| 2018-11-26 | sh.600000 | 浦发银行 |
| 2018-11-26 | sh.600016 | 民生银行 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| updateDate | 更新日期 |
| code | 证券代码 |
| code\_name | 证券名称 |




##### <a id="query_hs300_stocks"></a>沪深300成分股：query\_hs300\_stocks()

方法说明：通过API接口获取沪深300成分股信息，更新频率：每周一更新。返回类型：pandas的DataFrame类型。 使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取沪深300成分股
rs = bs.query_hs300_stocks()
print('query_hs300 error_code:'+rs.error_code)
print('query_hs300  error_msg:'+rs.error_msg)

# 打印结果集
hs300_stocks = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    hs300_stocks.append(rs.get_row_data())
result = pd.DataFrame(hs300_stocks, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/hs300_stocks.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()


```




参数含义：

* date：查询日期，格式XXXX-XX-XX，为空时默认最新日期。

返回示例数据

| updateDate | code | code\_name |
|------------|------------|-------|
| 2018-11-26 | sh.600000 | 浦发银行 |
| 2018-11-26 | sh.600008 | 首创股份 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| updateDate | 更新日期 |
| code | 证券代码 |
| code\_name | 证券名称 |




##### <a id="query_zz500_stocks"></a>中证500成分股：query\_zz500\_stocks()

方法说明：通过API接口获取中证500成分股信息，更新频率：每周一更新。返回类型：pandas的DataFrame类型。 使用示例

```

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取中证500成分股
rs = bs.query_zz500_stocks()
print('query_zz500 error_code:'+rs.error_code)
print('query_zz500  error_msg:'+rs.error_msg)

# 打印结果集
zz500_stocks = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    zz500_stocks.append(rs.get_row_data())
result = pd.DataFrame(zz500_stocks, columns=rs.fields)
# 结果集输出到csv文件
result.to_csv("D:/zz500_stocks.csv", encoding="gbk", index=False)
print(result)

# 登出系统
bs.logout()


```




参数含义：

* date：查询日期，格式XXXX-XX-XX，为空时默认最新日期。

返回示例数据

| updateDate | code | code\_name |
|------------|------------|-------|
| 2018-11-26 | sh.600004 | 白云机场 |
| 2018-11-26 | sh.600006 | 东风汽车 |

返回数据说明

| 参数名称 | 参数描述 |
|------------|------------|
| updateDate | 更新日期 |
| code | 证券代码 |
| code\_name | 证券名称 |




#### <a id="示例程序"></a>示例程序

##### <a id="example_query_history_k_data_plus"></a>获取指定日期全部股票的日K线数据

示例代码如下：

```

import baostock as bs
import pandas as pd


def download_data(date):
    bs.login()

    # 获取指定日期的指数、股票数据
    stock_rs = bs.query_all_stock(date)
    stock_df = stock_rs.get_data()
    data_df = pd.DataFrame()
    for code in stock_df["code"]:
        print("Downloading :" + code)
        k_rs = bs.query_history_k_data_plus(code, "date,code,open,high,low,close", date, date)
        data_df = data_df.append(k_rs.get_data())
    bs.logout()
    data_df.to_csv("D:\\demo_assignDayData.csv", encoding="gbk", index=False)
    print(data_df)


if __name__ == '__main__':
    # 获取指定日期全部股票的日K线数据
    download_data("2019-02-25")

---

<a id="baostock-document-003"></a>

## 3. A股K线数据

> 官方页面：[stockKData.md](https://baostock.com/mainContent?file=stockKData.md)

#### A股K线数据


##### 获取历史A股K线数据：query\_history\_k\_data\_plus()

方法说明：通过API接口获取A股历史交易数据，可以通过参数设置获取日k线、周k线、月k线，以及5分钟、15分钟、30分钟和60分钟k线数据，适合搭配均线数据进行选股和分析。

返回类型：pandas的DataFrame类型。

能获取1990-12-19至当前时间的数据；

可查询不复权、**前复权**、**后复权**数据。

示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_A_stock_k_data.xlsx)

日线使用示例：

```python
    
    import baostock as bs
    import pandas as pd
    
    #### 登陆系统 ####
    lg = bs.login()
    # 显示登陆返回信息
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)
    
    #### 获取沪深A股历史K线数据 ####
    # 详细指标参数，参见“历史行情指标参数”章节；“分钟线”参数与“日线”参数不同。“分钟线”不包含指数。
    # 分钟线指标：date,time,code,open,high,low,close,volume,amount,adjustflag
    # 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
    rs = bs.query_history_k_data_plus("sh.600000",
        "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
        start_date='2024-07-01', end_date='2024-12-31',
        frequency="d", adjustflag="3")
    print('query_history_k_data_plus respond error_code:'+rs.error_code)
    print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)
    
    #### 打印结果集 ####
    data_list = []
    while (rs.error_code == '0') & rs.next():
        # 获取一条记录，将记录合并在一起
        data_list.append(rs.get_row_data())
    result = pd.DataFrame(data_list, columns=rs.fields)
    
    #### 结果集输出到csv文件 ####   
    result.to_csv("D:\\history_A_stock_k_data.csv", index=False)
    print(result)
    
    #### 登出系统 ####
    bs.logout()

```


分钟线使用示例：

```python
    
    import baostock as bs
    import pandas as pd
    
    #### 登陆系统 ####
    lg = bs.login()
    # 显示登陆返回信息
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)
    
    #### 获取沪深A股历史K线数据 ####
    # 详细指标参数，参见“历史行情指标参数”章节；“分钟线”参数与“日线”参数不同。“分钟线”不包含指数。
    # 分钟线指标：date,time,code,open,high,low,close,volume,amount,adjustflag
    # 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
    rs = bs.query_history_k_data_plus("sh.600000",
        "date,time,code,open,high,low,close,volume,amount,adjustflag",
        start_date='2024-07-01', end_date='2024-12-31',
        frequency="5", adjustflag="3")
    print('query_history_k_data_plus respond error_code:'+rs.error_code)
    print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)
    
    #### 打印结果集 ####
    data_list = []
    while (rs.error_code == '0') & rs.next():
        # 获取一条记录，将记录合并在一起
        data_list.append(rs.get_row_data())
    result = pd.DataFrame(data_list, columns=rs.fields)
    
    #### 结果集输出到csv文件 ####   
    result.to_csv("D:\\history_A_stock_k_data.csv", index=False)
    print(result)
    
    #### 登出系统 ####
    bs.logout()

```


参数含义：

* code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
* fields：指示简称，支持多指标输入，以半角逗号分隔，填写内容作为返回类型的列。**详细指标列表见历史行情指标参数章节，日线与分钟线参数不同**。此参数不可为空；
* start：开始日期（包含），格式“YYYY-MM-DD”，为空时取2015-01-01；
* end：结束日期（包含），格式“YYYY-MM-DD”，为空时取最近一个交易日；
* frequency：数据类型，默认为d，日k线；d=日k线、w=周、m=月、5=5分钟、15=15分钟、30=30分钟、60=60分钟k线数据，不区分大小写；指数没有分钟线数据；周线每周最后一个交易日才可以获取，月线每月最后一个交易日才可以获取。
* adjustflag：**复权类型，默认不复权：3；1：后复权；2：前复权。已支持分钟线、日线、周线、月线前后复权。** BaoStock提供的是**涨跌幅复权算法**复权因子，具体介绍见[BaoStock复权因子简介](https://baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf "BaoStock复权因子简介.pdf")。



**注意：**

* 股票停牌时，对于日线，开、高、低、收价都相同，且都为前一交易日的收盘价，成交量、成交额为0，换手率为空。

如果需要将换手率转为float类型，可使用如下方法转换：result["turn"] = [0 if x == "" else float(x) for x in result["turn"]]



**关于复权数据的说明：**

BaoStock使用“涨跌幅复权法”进行复权，详细说明参考上文“复权因子简介”。不同系统间采用复权方式可能不一致，导致数据不一致。

“涨跌幅复权法的”优点：可以计算出资金收益率，确保初始投入的资金运用率为100%，既不会因为分红而导致投资减少，也不会因为配股导致投资增加。


与同花顺、通达信等存在不同。


返回示例数据

| date | code | open | high | low | close | preclose | volume | amount | adjustflag | turn | tradestatus | pctChg | isST |
|------------|------------|-------|------------|------------|-------|------------|------------|-------|------------|-------|------------|------------|-------|
| 2017-07-03 | sh.600000 | 12.64 | 12.65 | 12.47 | 12.56 | 12.65 | 38778949 | 486264672 | 3 | 0.137985 | 1 | —0.711456 | 0 |
| 2017-07-04 | sh.600000 | 12.55 | 12.58 | 12.41 | 12.55 | 12.56 | 36659128 | 458434432 | 3 | 0.130442 | 1 | —0.07962 | 0 |
| 2017-07-05 | sh.600000 | 12.5 | 12.65 | 12.47 | 12.62 | 12.55 | 26470507 | 332542464 | 3 | 0.094188 | 1 | 0.557767 | 0 |
| 2017-07-06 | sh.600000 | 12.62 | 12.72 | 12.51 | 12.66 | 12.62 | 37414241 | 471582096 | 3 | 0.133129 | 1 | 0.316957 | 0 |
| 2017-07-07 | sh.600000 | 12.62 | 12.69 | 12.55 | 12.6 | 12.66 | 24667294 | 311101536 | 3 | 0.087772 | 1 | —0.473929 | 0 |

返回数据说明

| 参数名称 | 参数描述 | 算法说明 |
|------------|------------|-------|
| date | 交易所行情日期 |  |
| code | 证券代码 |  |
| open | 开盘价 |  |
| high | 最高价 |  |
| low | 最低价 |  |
| close | 收盘价 |  |
| preclose | 前收盘价 | 见表格下方详细说明 |
| volume | 成交量（累计 单位：股） |  |
| amount | 成交额（单位：人民币元） |  |
| adjustflag | 复权状态(1：后复权， 2：前复权，3：不复权） |  |
| turn | 换手率 | [指定交易日的成交量(股)/指定交易日的股票的流通股总股数(股)]\*100% |
| tradestatus | 交易状态(1：正常交易 0：停牌） |  |
| pctChg | 涨跌幅（百分比） | 日涨跌幅=[(指定交易日的收盘价-指定交易日前收盘价)/指定交易日前收盘价]\*100% |
| peTTM | 滚动市盈率 | (指定交易日的股票收盘价/指定交易日的每股盈余TTM)=(指定交易日的股票收盘价\*截至当日公司总股本)/归属母公司股东净利润TTM |
| pbMRQ | 市净率 | (指定交易日的股票收盘价/指定交易日的每股净资产)=总市值/(最近披露的归属母公司股东的权益-其他权益工具) |
| psTTM | 滚动市销率 | (指定交易日的股票收盘价/指定交易日的每股销售额)=(指定交易日的股票收盘价\*截至当日公司总股本)/营业总收入TTM |
| pcfNcfTTM | 滚动市现率 | (指定交易日的股票收盘价/指定交易日的每股现金流TTM)=(指定交易日的股票收盘价\*截至当日公司总股本)/现金以及现金等价物净增加额TTM |
| isST | 是否ST股，1是，0否 |  |



**注意“前收盘价”说明**：


证券在指定交易日行情数据的前收盘价，当日发生除权除息时，“前收盘价”不是前一天的实际收盘价，而是根据股权登记日收盘价与分红现金的数量、配送股的数里和配股价的高低等结合起来算出来的价格。


具体计算方法如下:


1、计算除息价:


除息价=股息登记日的收盘价-每股所分红利现金额


2、计算除权价:


送红股后的除权价=股权登记日的收盘价/(1+每股送红股数)

配股后的除权价=(股权登记日的收盘价+配股价\*每股配股数)/(1+每股配股数)


3、计算除权除息价


除权除息价=(股权登记日的收盘价-每股所分红利现金额+配股价\*每股配股数)/(1+每股送红股数+每股配股数)

“前收盘价”由交易所计算并公布。首发日的“前收盘价”等于“首发价格”。


##### 历史行情指标参数


日线指标参数（包含停牌证券）

| 参数名称 | 参数描述 | 说明 |
|------------|------------|-------|
| date | 交易所行情日期 | 格式：YYYY-MM-DD |
| code | 证券代码 | 格式：sh.600000。sh：上海，sz：深圳 |
| open | 今开盘价格 | 精度：小数点后4位；单位：人民币元 |
| high | 最高价 | 精度：小数点后4位；单位：人民币元 |
| low | 最低价 | 精度：小数点后4位；单位：人民币元 |
| close | 今收盘价 | 精度：小数点后4位；单位：人民币元 |
| preclose | 昨日收盘价 | 精度：小数点后4位；单位：人民币元 |
| volume | 成交数量 | 单位：股 |
| amount | 成交金额 | 精度：小数点后4位；单位：人民币元 |
| adjustflag | 复权状态 | 不复权、前复权、后复权 |
| turn | 换手率 | 精度：小数点后6位；单位：% |
| tradestatus | 交易状态 | 1：正常交易 0：停牌 |
| pctChg | 涨跌幅（百分比） | 精度：小数点后6位 |
| peTTM | 滚动市盈率 | 精度：小数点后6位 |
| psTTM | 滚动市销率 | 精度：小数点后6位 |
| pcfNcfTTM | 滚动市现率 | 精度：小数点后6位 |
| pbMRQ | 市净率 | 精度：小数点后6位 |
| isST | 是否ST | 1是，0否 |

周、月线指标参数

| 参数名称 | 参数描述 | 说明 | 算法说明 |
|------------|------------|-------|-------|
| date | 交易所行情日期 | 格式：YYYY-MM-DD |  |
| code | 证券代码 | 格式：sh.600000。sh：上海，sz：深圳 |  |
| open | 开盘价格 | 精度：小数点后4位；单位：人民币元 |  |
| high | 最高价 | 精度：小数点后4位；单位：人民币元 |  |
| low | 最低价 | 精度：小数点后4位；单位：人民币元 |  |
| close | 收盘价 | 精度：小数点后4位；单位：人民币元 |  |
| volume | 成交数量 | 单位：股 |  |
| amount | 成交金额 | 精度：小数点后4位；单位：人民币元 |  |
| adjustflag | 复权状态 | 不复权、前复权、后复权 |  |
| turn | 换手率 | 精度：小数点后6位；单位：% |  |
| pctChg | 涨跌幅（百分比） | 精度：小数点后6位 | 涨跌幅=[(区间最后交易日收盘价-区间首个交易日前收盘价)/区间首个交易日前收盘价]\*100% |

5、15、30、60分钟线指标参数(不包含指数)

| 参数名称 | 参数描述 | 说明 |
|------------|------------|-------|
| date | 交易所行情日期 | 格式：YYYY-MM-DD |
| time | 交易所行情时间 | 格式：YYYYMMDDHHMMSSsss |
| code | 证券代码 | 格式：sh.600000。sh：上海，sz：深圳 |
| open | 开盘价格 | 精度：小数点后4位；单位：人民币元 |
| high | 最高价 | 精度：小数点后4位；单位：人民币元 |
| low | 最低价 | 精度：小数点后4位；单位：人民币元 |
| close | 收盘价 | 精度：小数点后4位；单位：人民币元 |
| volume | 成交数量 | 单位：股； 时间范围内的累计成交数量 |
| amount | 成交金额 | 精度：小数点后4位；单位：人民币元； 时间范围内的累计成交金额 |
| adjustflag | 复权状态 | 不复权、前复权、后复权 |

---

<a id="baostock-document-004"></a>

## 4. 每日更新

> 官方页面：[DailyUpdates.md](https://baostock.com/mainContent?file=DailyUpdates.md)

##### 每日更新

#### 目录
  
* [1 获取每日数据](#获取每日数据)
  + [1.1 获取某日所有股票日K线数据：query_daily_history_k_AStock()](#query_daily_history_k_AStock)
  + [1.2 获取某日所有ETF日K线数据：query_daily_history_k_ETF](#query_daily_history_k_ETF)
  + [1.3 获取某日复权因子信息：query_daily_adjust_factor](#query_daily_adjust_factor)


#### <a id="获取每日数据"></a>获取每日数据

##### <a id="query_daily_history_k_AStock"></a>获取某日所有股票日K线数据：query\_daily\_history\_k\_AStock()

方法说明：通过API接口获取A股历史交易数据，可以通过参数设置获取指定日期A股日k线数据，适合搭配均线数据进行选股和分析。

返回类型：pandas的DataFrame类型。

使用示例：

```python

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取某日所有股票日K线数据 ####
#返回字段：date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST
rs = bs.query_daily_history_k_AStock(date='2026-02-05') #
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
print('query_daily_history_k_AStock respond error_code:'+rs.error_code)
print('query_daily_history_k_AStock respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

#### 结果集输出到csv文件 ####
result.to_csv("D:/daily_history_k_AStock_data.csv", encoding="gbk", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```


参数含义：

* date：获取日期，格式“YYYY-MM-DD”，为空时取当前自然日；

**注意：**

* 股票停牌时，对于日线，开、高、低、收价都相同，且都为前一交易日的收盘价，成交量、成交额为0，换手率为空。

如果需要将换手率转为float类型，可使用如下方法转换：result["turn"] = [0 if x == "" else float(x) for x in result["turn"]]


返回示例数据

| date       | code       | open    | high    | low     | close   | preclose | volume     | amount        | adjustflag | turn     | tradestatus | pctChg    | peTTM      | pbMRQ    | psTTM    | pcfNcfTTM    | isST |
|------------|------------|---------|---------|---------|---------|----------|------------|---------------|------------|----------|-------------|-----------|------------|----------|----------|--------------|------|
| 2026-02-05 | sh.600648  | 10.7000 | 10.7800 | 10.6400 | 10.7400 | 10.6800  | 4465487    | 47925519.1900 | 3          | 0.392500 | 1           | 0.561800  | 21.493688  | 0.962863 | 2.226877 | -58.658491   | 0    |
| 2026-02-05 | sh.600649  | 5.5200  | 5.7800  | 5.4600  | 5.6400  | 5.5500   | 106503170  | 598013239.0900| 3          | 4.252500 | 1           | 1.621600  | 18.947748  | 0.670040 | 0.783396 | 18.948974    | 0    |
| 2026-02-05 | sh.600650  | 15.1800 | 15.3500 | 15.1200 | 15.2500 | 15.2600  | 3477800    | 52978520.0000 | 3          | 0.890500 | 1           | -0.065500 | 67.776938  | 1.964848 | 4.942318 | 53.735923    | 0    |
| 2026-02-05 | sh.600651  | 8.0100  | 8.1000  | 7.9000  | 8.0100  | 8.0500   | 18066100   | 144088874.0000| 3          | 0.720600 | 1           | -0.496900 | 404.504618 | 8.055464 | 10.498675| 151.923309   | 0    |

返回数据说明

| 参数名称     | 参数描述                     | 算法说明                                                                 |
|--------------|------------------------------|--------------------------------------------------------------------------|
| date         | 交易所行情日期               |                                              |
| code         | 证券代码                     |                   |
| open         | 开盘价                       |                                           |
| high         | 最高价                       |                                                 |
| low          | 最低价                       |                                              |
| close        | 收盘价                       |                                           |
| preclose     | 前收盘价                     | 见表格下方详细说明                                |
| volume       | 成交量（累计，单位：股）     |                                                    |
| amount       | 成交额（单位：人民币元）     |                                             |
| adjustflag   | 复权状态（1：后复权，2：前复权，3：不复权）|                           |
| turn         | 换手率                       | [指定交易日的成交量(股)/指定交易日的股票的流通股总数(股)]*100%                        |
| tradestatus  | 交易状态（1：正常交易，0：停牌）  |                                          |
| pctChg       | 涨跌幅（百分比）             | 日涨跌幅=[(指定交易日的收盘价-指定交易日前收盘价)/指定交易日前收盘价]*100%                   |
| peTTM        | 滚动市盈率                   | (指定交易日的股票收盘价/指定交易日的每股盈余TTM)=(指定交易日的股票收盘价*截至当日公司总股本)/归属母公司股东净利润TTM                 |
| pbMRQ        | 市净率                       | (指定交易日的股票收盘价/指定交易日的每股净资产)=总市值/(最近披露的归属母公司股东的权益-其他权益工具)                  |
| psTTM        | 滚动市销率                   | (指定交易日的股票收盘价/指定交易日的每股销售额)=(指定交易日的股票收盘价*截至当日公司总股本)/营业总收入TTM                             |
| pcfNcfTTM    | 滚动市现率                   | (指定交易日的股票收盘价/指定交易日的每股现金流TTM)=(指定交易日的股票收盘价*截至当日公司总股本)/现金以及现金等价物净增加额TTM              |
| isST         | 是否ST股,1：是，0：否                    |                                                 |



##### <a id="query_daily_history_k_ETF"></a>获取某日所有ETF日K线数据：query\_daily\_history\_k\_ETF()

方法说明：通过API接口获取ETF历史交易数据，可以通过参数设置获取指定日期ETF日k线数据，适合搭配均线数据进行选股和分析。

返回类型：pandas的DataFrame类型。

使用示例：

```python

import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取某日所有ETF日K线数据 ####
#返回字段：date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST
rs = bs.query_daily_history_k_ETF(date='2026-02-05')  #
print('query_daily_history_k_ETF respond error_code:'+rs.error_code)
print('query_daily_history_k_ETF respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

#### 结果集输出到csv文件 ####
result.to_csv("D:/daily_history_k_ETF_data.csv", encoding="gbk", index=False)
print(result)

#### 登出系统 ####
bs.logout()

```


参数含义：

* date：获取日期，格式“YYYY-MM-DD”，为空时取当前自然日；

**注意：**

* 股票停牌时，对于日线，开、高、低、收价都相同，且都为前一交易日的收盘价，成交量、成交额为0，换手率为空。

如果需要将换手率转为float类型，可使用如下方法转换：result["turn"] = [0 if x == "" else float(x) for x in result["turn"]]


返回示例数据

| date         | code      | open   | high   | low    | close  | preclose | volume  | amount      | adjustflag | turn     | tradestatus | pctChg    | peTTM | pbMRQ | psTTM | pcfNcfTTM | isST |
|--------------|-----------|--------|--------|--------|--------|----------|---------|-------------|------------|----------|-------------|-----------|-------|-------|-------|-----------|------|
| 2026-02-05 | sh.510010 | 1.8230 | 1.8280 | 1.8180 | 1.8280 | 1.8290   | 59000   | 107477.0000 | 3          | 0.041986 | 1           | -0.054700 |       |       |       |           | 1    |
| 2026-02-05 | sh.510020 | 3.8450 | 3.8810 | 3.8450 | 3.8780 | 3.8840   | 265300  | 1025309.0000| 3          | 0.740069 | 1           | -0.154500 |       |       |       |           | 1    |
| 2026-02-05 | sh.510030 | 1.0830 | 1.0910 | 1.0770 | 1.0870 | 1.0820   | 4610000 | 4990416.0000| 3          | 2.748468 | 1           | 0.462100  |       |       |       |           | 1    |
| 2026-02-05 | sh.510040 | 1.2060 | 1.2090 | 1.1960 | 1.2050 | 1.2120   | 346500  | 416305.0000 | 3          | 1.004930 | 1           | -0.577600 |       |       |       |           | 1    |



返回数据说明

| 参数名称     | 参数描述                     | 算法说明                                                                 |
|--------------|------------------------------|--------------------------------------------------------------------------|
| date         | 交易所行情日期               |                                              |
| code         | 证券代码                     |                   |
| open         | 开盘价                       |                                           |
| high         | 最高价                       |                                                 |
| low          | 最低价                       |                                              |
| close        | 收盘价                       |                                           |
| preclose     | 前收盘价                     | 见表格下方详细说明                                |
| volume       | 成交量（累计，单位：股）     |                                                    |
| amount       | 成交额（单位：人民币元）     |                                             |
| adjustflag   | 复权状态（1：后复权，2：前复权，3：不复权）|                           |
| turn         | 换手率                       | [指定交易日的成交量(股)/指定交易日的股票的流通股总数(股)]*100%                        |
| tradestatus  | 交易状态（1：正常交易，0：停牌）  |                                          |
| pctChg       | 涨跌幅（百分比）             | 日涨跌幅=[(指定交易日的收盘价-指定交易日前收盘价)/指定交易日前收盘价]*100%                   |
| peTTM        | 滚动市盈率                   | (指定交易日的股票收盘价/指定交易日的每股盈余TTM)=(指定交易日的股票收盘价*截至当日公司总股本)/归属母公司股东净利润TTM                 |
| pbMRQ        | 市净率                       | (指定交易日的股票收盘价/指定交易日的每股净资产)=总市值/(最近披露的归属母公司股东的权益-其他权益工具)                  |
| psTTM        | 滚动市销率                   | (指定交易日的股票收盘价/指定交易日的每股销售额)=(指定交易日的股票收盘价*截至当日公司总股本)/营业总收入TTM                             |
| pcfNcfTTM    | 滚动市现率                   | (指定交易日的股票收盘价/指定交易日的每股现金流TTM)=(指定交易日的股票收盘价*截至当日公司总股本)/现金以及现金等价物净增加额TTM              |
| isST         | 是否ST股,1：是，0：否                    |                                                 |


##### <a id="query_daily_adjust_factor"></a>获取某日复权因子信息：query\_daily\_adjust\_factor()

方法说明：通过API接口获取指定日期复权因子信息数据。

返回类型：pandas的DataFrame类型。

使用示例：

```python

import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

# 获取某日复权因子信息
rs_list = []
#返回字段：code, dividOperateDate, foreAdjustFactor, backAdjustFactor, adjustFactor
rs_factor = bs.query_daily_adjust_factor(date="2026-02-05") #
print('query_daily_adjust_factor respond error_code:'+rs_factor.error_code)
print('query_daily_adjust_factor respond  error_msg:'+rs_factor.error_msg)

while (rs_factor.error_code == '0') & rs_factor.next():
    # 获取一条记录，将记录合并在一起
    rs_list.append(rs_factor.get_row_data())
result = pd.DataFrame(rs_list, columns=rs_factor.fields)
# 打印输出
print(result)

# 结果集输出到csv文件
result.to_csv("D:\\daily_adjust_factor_data.csv", encoding="gbk", index=False)

# 登出系统
bs.logout()


```


参数含义：

* date：获取日期，格式“YYYY-MM-DD”，为空时取当前自然日；

**注意：**


如果需要将换手率转为float类型，可使用如下方法转换：result["turn"] = [0 if x == "" else float(x) for x in result["turn"]]


返回示例数据

| code       | dividOperateDate | foreAdjustFactor | backAdjustFactor | adjustFactor |
|------------|------------------|------------------|------------------|--------------|
| sh.601818  | 2026-02-05       | 1.000000         | 2.072976         | 2.072976     |
| sh.601860  | 2026-02-05       | 0.980989         | 1.257941         | 1.257941     |
| sh.603019  | 2026-02-05       | 0.995693         | 4.082735         | 4.082735     |
| sh.603727  | 2026-02-05       | 0.991643         | 1.109671         | 1.109671     |

返回数据说明

| 参数名称     | 参数描述                     | 算法说明                                                                 |
|--------------|------------------------------|--------------------------------------------------------------------------|
| code | 证券代码 | |
| dividOperateDate | 除权除息日期 | |
| foreAdjustFactor | 向前复权因子 | 除权除息日前一个交易日的收盘价 / 除权除息日最近的一个交易日的前收盘价 |
| backAdjustFactor | 向后复权因子 | 除权除息日最近的一个交易日的前收盘价 / 除权除息日前一个交易日的收盘价 |
| adjustFactor | 本次复权因子 | |

---

<a id="baostock-document-005"></a>

## 5. PY开发资源

> 官方页面：[pythonDevRes.md](https://baostock.com/mainContent?file=pythonDevRes.md)

#### Python开发资源
**BaoStock新手入门**
___
[Python安装教程](https://baostock.com/helpdocs/pdf/Python%E5%AE%89%E8%A3%85%E6%95%99%E7%A8%8B.pdf "Python安装教程.pdf")&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[BaoStock的安装与使用](https://baostock.com/helpdocs/pdf/BaoStock%E7%9A%84%E5%AE%89%E8%A3%85%E4%B8%8E%E4%BD%BF%E7%94%A8.pdf "BaoStock的安装与使用.pdf")<br />

<br>
<br>

**本地程序化交易框架**
___
[BaoStock](http://www.baostock.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Pandas](https://github.com/pandas-dev/pandas)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[ApolloAuto](https://www.oschina.net/p/apolloauto)

财经数据接口包&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Python数据分析包&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;开源自动驾驶平台

<br>
<br>

**Python人工智能算法库**
___
[TensorFlow中文社区](http://www.tensorfly.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[TensorFlow Github仓库](https://github.com/tensorflow/tensorflow)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Nvidia CUDA](http://www.nvidia.cn/object/cudazone-cn.html)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Theano深度学习库](http://deeplearning.net/software/theano/)

Goole出的深度学习库，阿尔法狗&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Goole出的深度学习库，阿尔法狗&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;采用NVIDIA显卡并行计算的库&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;在Python环境下编写深度学习
<br>
<br>
[Theano Github仓库](https://github.com/Theano/Theano)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Scikit-learn](https://scikit-learn.org/stable/index.html)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[CNTK](https://www.microsoft.com/en-us/cognitive-toolkit/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[亚马逊机器学习范例代码](https://github.com/aws-samples/machine-learning-samples)

在Python环境下编写深度学习&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;回归和聚类的算法包括支持向量机，逻辑回&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;微软深度学习库&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;好玩易用掌上美图工具

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;归，朴素贝叶斯分类器，随机森林
<br>
<br>
[Pylearn2深度学习库](http://deeplearning.net/software/pylearn2/)

基于Theano深度学习常见模型和训练算法

<br>

**八大国家级交易所**
___
[上海证券交易所](http://www.sse.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[深圳证券交易所](http://www.szse.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[新三板](http://www.neeq.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[中国金融期货交易所](http://www.cffex.com.cn/)

上海证券交易所官网&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;深圳证券交易所官网&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;全国中小企业股份转让系统&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;金交所官网
<br>
<br>
[上海期货交易所](http://www.shfe.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[大连商品交易所](http://www.dce.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[郑州商品交易所](http://www.czce.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[上海黄金交易所](http://www.sge.com.cn/)

上海期货交易所官网&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;大连商品交易所官网&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;郑州商品交易所官网&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;上海黄金交易所官网

<br>

**搜索引擎和工具**
___
[百度](https://www.baidu.com)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[谷歌翻译](https://translate.google.cn)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[百度翻译](https://fanyi.baidu.com)

百度搜索&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;翻译工具&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;翻译工具

<br>

**量化交易社区**
___
[知乎](https://www.zhihu.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[腾讯财经](https://new.qq.com/ch/finance/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[新浪财经](http://finance.sina.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[搜狐财经](http://business.sohu.com/)

发现更大的世界&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;腾讯旗下金融网站&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;新浪旗下金融网站&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;搜狐旗下金融网站

<br>

[水木社区](http://www.newsmth.net/nForum/#!board/ProgramTrading)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[雪球](https://xueqiu.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[优矿量化社区](https://uqer.io/community/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[米筐社区](https://www.ricequant.com/community/category/all)

象牙塔通向社会的桥梁&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;聪明的投资者都在这里&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;优矿在线回测平台旗下社区&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;米筐在线回测平台旗下社区

<br>

[聚宽](https://www.joinquant.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[大数据人](http://www.bigdata.ren/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[股吧](http://guba.eastmoney.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[金融界](http://www.jrj.com.cn/)

聪明的投资者都在这里&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;大数据社区&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;东方财富网旗下社区&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;创新性互联网证券服务

<br>

[和讯网](http://www.hexun.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[A股交易工具社区](http://www.tdxapi.com/comm/)

早期金融证券资讯服务&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;QuicklibTrade和TdxApi社区

<br>

**在线回测平台**
___
[优矿](https://uqer.io/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[米筐](https://www.ricequant.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[聚宽](https://www.joinquant.com/)

老牌在线回测平台&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;为人熟知的在线回测平台&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;不错的在线回测平台

<br>

**基金业绩展示平台、基金销售平台**
___
[私募排排网](http://www.simuwang.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[格上财富](https://www.licai.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[好买基金网](https://www.howbuy.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[支付宝](https://www.alipay.com/)

查排名，买私募，看路演&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;研究驱动的专业财富管理公司&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;十年成长，忠于真实&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;支付宝

<br>

[陆金所](https://www.lu.com/)

互联网财富管理平台

<br>

**数据源**
___
[BaoStock(免费)](http://www.baostock.com)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Historical Data Sources](https://quantpedia.com/Links/HistoricalData)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[新浪Level2行情(收费)](http://finance.sina.com.cn/stock/level2/orderIntro.html)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Quandl](https://www.quandl.com/)

免费、开源的证券数据平台&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;一个外盘数据源索引&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;数据服务中心&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;国际金融和经济数据

<br>

[Wind资讯(收费)](http://www.wind.com.cn/NewSite/edb.html)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[东方财富 Choice(收费)](http://link.zhihu.com/?target=http%3A//choice.eastmoney.com/Product/index.html)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[iFinD(收费)](http://link.zhihu.com/?target=http%3A//www.51ifind.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[朝阳永续(收费)](http://www.go-goal.cn/)

经济数据库&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;金融数据研究终端&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;同花顺金融数据终端&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Go-Goal数据终端

<br>

[天软数据(收费)](http://www.tinysoft.com.cn/TSDN/HomePage.tsl)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[预测者网(收费)](https://www.yucezhe.com/product/data/trading)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[锐思数据(收费)](http://www.resset.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[恒生API(收费)](https://www.hs.net/)

站长提交资源的绿色通道&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;互联网时代的金融数据服务&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;专业数据&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;恒生数据

<br>

[Bloomberg API(收费)](https://www.bloomberglabs.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[数库金融数据(收费)](http://developer.chinascope.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[巨潮资讯(收费)](http://www.cninfo.com.cn/new/index)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[通联数据商城(收费)](https://www2.datayes.com/)

获得新客户和合作伙伴&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;和深度分析API服务&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;大数据营销决策平台&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;优矿旗下数据商城

<br>

[万德(收费)](http://www.wind.com.cn/)

优矿旗下数据商城

<br>

**行情交易软件**
___
[大智慧](http://www.gw.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[同花顺](http://www.10jqka.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[通达信](http://www.tdx.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[钱龙](http://www.ql18.com.cn/)

大智慧行情交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;同花顺行情交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;通达信行情交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;老牌股票软件
<br>
<br>
[益盟操盘手](http://product.emoney.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[指南针](http://qy.compass.cn/fenfen2.php)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[文华财经](http://www.wenhua.com.cn/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[金字塔](http://www.weistock.com/)

行情交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;老牌行情交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;期货行情交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;金字塔行情交易软件
<br>
<br>
[TB交易开拓者](http://www.tradeblazer.net/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[酷操盘手](http://www.kucps.com/)

期货程序化交易软件&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;期货CTP多账户程序化交易跟单软件

<br>

**金融人才招聘**
___
[51job](https://www.51job.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[智联招聘](https://www.zhaopin.com/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[中华英才网](http://www.chinahr.com/home/sh/)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[赶集网招聘](http://sh.ganji.com/)

好工作尽在前程无忧&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;更懂你的价值&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;专注于年轻精英白领招聘&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;赶集网招聘
<br>
<br>

---

<a id="baostock-document-006"></a>

## 6. 指数数据

> 官方页面：[indexData.md](https://baostock.com/mainContent?file=indexData.md)


#### 指数数据

通过API接口获取指数(综合指数、规模指数、一级行业指数、二级行业指数、策略指数、成长指数、价值指数、主题指数)K线数据。 

     1. 综合指数，例如：sh.000001 上证指数，sz.399106 深证综指 等；
     2. 规模指数，例如：sh.000016 上证50，sh.000300 沪深300，sh.000905 中证500，sz.399001 深证成指等；
     3. 一级行业指数，例如：sh.000037 上证医药，sz.399433 国证交运 等；
     4. 二级行业指数，例如：sh.000952 300地产，sz.399951 300银行 等；
     5. 策略指数，例如：sh.000050 50等权，sh.000982 500等权 等；
     6. 成长指数，例如：sz.399376 小盘成长 等；
     7. 价值指数，例如：sh.000029 180价值 等；
     8. 主题指数，例如：sh.000015 红利指数，sh.000063 上证周期 等；
     9. 基金指数，例如：sh.000011 上证基金指数 等；
     10. 债券指数，例如：sh.000012 上证国债指数 等；



#### 沪深指数K线数据 示例

指数未提供分钟线数据。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_Index_k_data.xlsx)
    
```python
    import baostock as bs
    import pandas as pd
    
    # 登陆系统
    lg = bs.login()
    # 显示登陆返回信息
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)
    
    # 获取指数(综合指数、规模指数、一级行业指数、二级行业指数、策略指数、成长指数、价值指数、主题指数)K线数据
    # 综合指数，例如：sh.000001 上证指数，sz.399106 深证综指 等；
    # 规模指数，例如：sh.000016 上证50，sh.000300 沪深300，sh.000905 中证500，sz.399001 深证成指等；
    # 一级行业指数，例如：sh.000037 上证医药，sz.399433 国证交运 等；
    # 二级行业指数，例如：sh.000952 300地产，sz.399951 300银行 等；
    # 策略指数，例如：sh.000050 50等权，sh.000982 500等权 等；
    # 成长指数，例如：sz.399376 小盘成长 等；
    # 价值指数，例如：sh.000029 180价值 等；
    # 主题指数，例如：sh.000015 红利指数，sh.000063 上证周期 等；
    
    
    # 详细指标参数，参见“历史行情指标参数”章节；“周月线”参数与“日线”参数不同。
    # 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
    rs = bs.query_history_k_data_plus("sh.000001",
        "date,code,open,high,low,close,preclose,volume,amount,pctChg",
        start_date='2017-01-01', end_date='2017-06-30', frequency="d")
    print('query_history_k_data_plus respond error_code:'+rs.error_code)
    print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)
    
    # 打印结果集
    data_list = []
    while (rs.error_code == '0') & rs.next():
        # 获取一条记录，将记录合并在一起
        data_list.append(rs.get_row_data())
    result = pd.DataFrame(data_list, columns=rs.fields)
    # 结果集输出到csv文件
    result.to_csv("D:\\history_Index_k_data.csv", index=False)
    print(result)
    
    # 登出系统
    bs.logout()
    
```
参数含义： 

  * code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
  * fields：指示简称，支持多指标输入，以半角逗号分隔，填写内容作为返回类型的列。**详细指标列表见历史行情指标参数章节** 。此参数不可为空；
  * start：开始日期（包含），格式“YYYY-MM-DD”，为空时取2015-01-01；
  * end：结束日期（不包含），格式“YYYY-MM-DD”，为空时取最近一个交易日；
  * frequency：数据类型，默认为d，日k线；d=日k线、w=周、m=月、5=5分钟、15=15分钟、30=30分钟、60=60分钟k线数据，不区分大小写；指数没有分钟线数据；周线每周最后一个交易日才可以获取，月线第月最后一个交易日才可以获取。

返回示例数据

|date  | code  | open  | high  | low  | close  | preclose  | volume  | amount  | pctChg   
---|---|---|---|---|---|---|---|---|---  
2017-01-03  | sh.000001  | 3105.3080  | 3136.4550  | 3105.3080  | 3135.9200  | 3103.6370  | 14156718592  | 159887138816.0000  | 1.040200   
2017-01-04  | sh.000001  | 3133.7870  | 3160.1020  | 3130.1140  | 3158.7940  | 3135.9200  | 16786085120  | 195914293248.0000  | 0.729400   
  
  

返回数据说明

|参数名称  | 参数描述  | 说明   
---|---|---  
date  | 交易所行情日期  | 格式：YYYY-MM-DD   
code  | 证券代码  | 格式：sh.600000。sh：上海，sz：深圳   
open  | 今开盘价格  | 精度：小数点后4位；单位：人民币元   
high  | 最高价  | 精度：小数点后4位；单位：人民币元   
low  | 最低价  | 精度：小数点后4位；单位：人民币元   
close  | 今收盘价  | 精度：小数点后4位；单位：人民币元   
preclose  | 昨日收盘价  | 精度：小数点后4位；单位：人民币元   
volume  | 成交数量  | 单位：股   
amount  | 成交金额  | 精度：小数点后4位；单位：人民币元   
pctChg  | 涨跌幅  | 精度：小数点后6位

---

<a id="baostock-document-007"></a>

## 7. 估值指标(日频)

> 官方页面：[valuationDaily.md](https://baostock.com/mainContent?file=valuationDaily.md)


#### 估值指标(日频)

#### 沪深A股估值指标(日频) 示例

通过query_history_k_data_plus()获取沪深A股估值指标(日频)数据（指数未提供估值数据），未提供周、月估值数据。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_A_stock_valuation_indicator_data.xlsx)
    

```python
    import baostock as bs
    import pandas as pd
    
    #### 登陆系统 ####
    lg = bs.login()
    # 显示登陆返回信息
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)
    
    #### 获取沪深A股估值指标(日频)数据 ####
    # peTTM    滚动市盈率
    # psTTM    滚动市销率
    # pcfNcfTTM    滚动市现率
    # pbMRQ    市净率
    rs = bs.query_history_k_data_plus("sh.600000",
        "date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM",
        start_date='2015-01-01', end_date='2017-12-31', 
        frequency="d", adjustflag="3")
    print('query_history_k_data_plus respond error_code:'+rs.error_code)
    print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)
    
    #### 打印结果集 ####
    result_list = []
    while (rs.error_code == '0') & rs.next():
        # 获取一条记录，将记录合并在一起
        result_list.append(rs.get_row_data())
    result = pd.DataFrame(result_list, columns=rs.fields)
    
    #### 结果集输出到csv文件 ####
    result.to_csv("D:\\history_A_stock_valuation_indicator_data.csv", encoding="gbk", index=False)
    print(result)
    
    #### 登出系统 ####
    bs.logout()
```

    

返回数据说明

| 参数名称      | 参数描述  | 说明   
-----------|---|---  
 date      | 交易所行情日期  | 格式：YYYY-MM-DD   
 code      | 证券代码  | 格式：sh.600000。sh：上海，sz：深圳   
 close     | 今收盘价  | 精度：小数点后4位；单位：人民币元   
 peTTM     | 滚动市盈率  | 精度：小数点后4位   
 psTTM     | 滚动市销率  | 精度：小数点后4位   
 pcfNcfTTM | 滚动市现率  | 精度：小数点后4位   
 pbMRQ     | 市净率  | 精度：小数点后4位

---

<a id="baostock-document-008"></a>

## 8. 除权除息信息

> 官方页面：[dividInfo.md](https://baostock.com/mainContent?file=dividInfo.md)


#### 除权除息信息

##### 除权除息信息：query_dividend_data()

通过API接口获取除权除息信息数据（预披露、预案、正式都已通过）。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/history_Dividend_data.xlsx)
    
```python
    import baostock as bs
    import pandas as pd
    
    #### 登陆系统 ####
    lg = bs.login()
    # 显示登陆返回信息
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)
    
    #### 查询除权除息信息####
    # 查询2015年除权除息信息
    rs_list = []
    rs_dividend_2015 = bs.query_dividend_data(code="sh.600000", year="2015", yearType="report")
    while (rs_dividend_2015.error_code == '0') & rs_dividend_2015.next():
        rs_list.append(rs_dividend_2015.get_row_data())
    
    # 查询2016年除权除息信息
    rs_dividend_2016 = bs.query_dividend_data(code="sh.600000", year="2016", yearType="report")
    while (rs_dividend_2016.error_code == '0') & rs_dividend_2016.next():
        rs_list.append(rs_dividend_2016.get_row_data())
    
    # 查询2017年除权除息信息
    rs_dividend_2017 = bs.query_dividend_data(code="sh.600000", year="2017", yearType="report")
    while (rs_dividend_2017.error_code == '0') & rs_dividend_2017.next():
        rs_list.append(rs_dividend_2017.get_row_data())
    
    result_dividend = pd.DataFrame(rs_list, columns=rs_dividend_2017.fields)
    # 打印输出
    print(result_dividend)
    
    #### 结果集输出到csv文件 ####   
    result_dividend.to_csv("D:\\history_Dividend_data.csv", encoding="gbk",index=False)
    
    #### 登出系统 ####
    bs.logout()
```

参数含义： 

  * code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
  * year：年份，如：2017。此参数不可为空；
  * yearType：年份类别，默认为"report":预案公告年份，可选项"operate":除权除息年份。此参数不可为空。

返回示例数据

| code  | dividPreNoticeDate  | dividAgmPumDate  | dividPlanAnnounceDate  | dividPlanDate  | dividRegistDate  | dividOperateDate  | dividPayDate   
---|---|---|---|---|---|---|---  
sh.600000  |  | 2015-05-16  | 2015-03-19  | 2015-06-16  | 2015-06-19  | 2015-06-23  | 2015-06-23   
sh.600000  |  | 2016-04-29  | 2016-04-07  | 2016-06-16  | 2016-06-22  | 2016-06-23  | 2016-06-23   
sh.600000  |  | 2017-04-26  | 2017-04-01  | 2017-05-19  | 2017-05-24  | 2017-05-25  | 2017-05-25   

返回示例数据 

| dividStockMarketDate | dividCashPsBeforeTax  | dividCashPsAfterTax  | dividStocksPs  | dividCashStock  | dividReserveToStockPs   
----------------------|---|---|---|---|---  
| 0.757                | 0.6813或0.71915  | 0.000000  | 10派7.57元（含税，扣税后6.813或7.1915元）  |   
 2016-06-24           | 0.515  | 0.4635或0.515  | 0.000000  | 10转1派5.15元（含税，扣税后4.635或5.15元）  | 0.100000   
 2017-05-26           | 0.2  | 0.18或0.2  | 0.000000  | 10转3派2元（含税，扣税后1.8或2元）  | 0.300000   
  
  


返回数据说明

|参数名称  | 参数描述  | 算法说明   
---|---|---  
code  | 证券代码  |   
dividPreNoticeDate  | 预批露公告日  |   
dividAgmPumDate  | 股东大会公告日期  |   
dividPlanAnnounceDate  | 预案公告日  |   
dividPlanDate  | 分红实施公告日  |   
dividRegistDate  | 股权登记告日  |   
dividOperateDate  | 除权除息日期  |   
dividPayDate  | 派息日  |   
dividStockMarketDate  | 红股上市交易日  |   
dividCashPsBeforeTax  | 每股股利税前  | 派息比例分子(税前)/派息比例分母   
dividCashPsAfterTax  | 每股股利税后  | 派息比例分子(税后)/派息比例分母   
dividStocksPs  | 每股红股  |   
dividCashStock  | 分红送转  | 每股派息数(税前)+每股送股数+每股转增股本数   
dividReserveToStockPs  | 每股转增资本  |

---

<a id="baostock-document-009"></a>

## 9. 复权因子信息

> 官方页面：[factorInfo.md](https://baostock.com/mainContent?file=factorInfo.md)


#### 复权因子信息

##### 复权因子：query_adjust_factor()


通过API接口获取复权因子信息数据。示例数据：[<button>下载</button>](https://baostock.com/helpdocs/csv/adjust_factor_data.xlsx)

BaoStock提供的是**涨跌幅复权算法** 复权因子，具体介绍见：[媒体文件:BaoStock复权因子简介.pdf](https://baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf "BaoStock复权因子简介.pdf")。   

基于BaoStock复权因子与本地BaoStock日K线数据**生成复权行情**，具体介绍见：<a href="https://www.baostock.com/mainContent?file=localdatafactorInfo.md" style="color:#000; font-weight:bold;">利用本地Baostock日K线数据手动计算复权价格</a>。 


```python
    import baostock as bs
    import pandas as pd
    
    # 登陆系统
    lg = bs.login()
    # 显示登陆返回信息
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)
    
    # 查询2015至2017年复权因子
    rs_list = []
    rs_factor = bs.query_adjust_factor(code="sh.600000", start_date="2015-01-01", end_date="2017-12-31")
    while (rs_factor.error_code == '0') & rs_factor.next():
        rs_list.append(rs_factor.get_row_data())
    result_factor = pd.DataFrame(rs_list, columns=rs_factor.fields)
    # 打印输出
    print(result_factor)
    
    # 结果集输出到csv文件
    result_factor.to_csv("D:\\adjust_factor_data.csv", encoding="gbk", index=False)
    
    # 登出系统
    bs.logout()
```

参数含义： 

  * code：股票代码，sh或sz.+6位数字代码，或者指数代码，如：sh.601398。sh：上海；sz：深圳。此参数不可为空；
  * start_date：开始日期，为空时默认为2015-01-01，包含此日期；
  * end_date：结束日期，为空时默认当前日期，包含此日期。

返回示例数据

| code             | dividOperateDate  | foreAdjustFactor  | backAdjustFactor  | adjustFactor   
------------------|---|---|---|---  
 sh.600000        | 2015-06-23  | 0.663792  | 6.295967  | 6.295967   
 sh.600000        | 2016-06-23  | 0.751598  | 7.128788  | 7.128788   
 sh.600000        | 2017-05-25  | 0.989551  | 9.385732  | 9.385732   
 
返回数据说明 

| 参数名称     | 参数描述  | 算法说明   
 ---              |---|---  
 code             | 证券代码  |   
 dividOperateDate | 除权除息日期  |   
 foreAdjustFactor | 向前复权因子  | 除权除息日前一个交易日的收盘价/除权除息日最近的一个交易日的前收盘价   
 backAdjustFactor | 向后复权因子  | 除权除息日最近的一个交易日的前收盘价/除权除息日前一个交易日的收盘价   
 adjustFactor     | 本次复权因子  |

---

<a id="baostock-document-010"></a>

## 10. 本地计算前复权

> 官方页面：[localdatafactorInfo.md](https://baostock.com/mainContent?file=localdatafactorInfo.md)


#### 利用本地Baostock日K线数据手动计算复权价格

在量化策略回测中，复权数据是保证价格连续性的基础。为避免频繁请求BaoStock API，可通过BaoStock复权因子(<a href="https://www.baostock.com/mainContent?file=factorInfo.md" style="color:#000; font-weight:bold;">BaoStock复权因子获取方法见：query_adjust_factor()</a>)与本地存储的原始日K线数据(<a href="https://www.baostock.com/mainContent?file=stockKData.md" style="color:#000; font-weight:bold;">日K线获取方法见：query_history_k_data_plus()</a>)自行计算复权价格（分钟线同理）。[媒体文件:利用BaoStock本地日K线数据手动计算复权价格.pdf](https://baostock.com/helpdocs/pdf/BaoStock前复权日K线数据计算简介.pdf)
本文以浦发银行（sh.600000）为例，展示 2014-01-01 至 2020-01-01 区间内，基于BaoStock复权因子计算前复权日 K 线的完整流程（后复权方法类似）。 


```python
import baostock as bs
import pandas as pd

# 初始化baostock
lg = bs.login()

# 定义股票代码和时间范围
stock_code = "sh.600000"  # 浦发银行
start_date = "2014-01-01"
end_date = "2020-01-01"

# 1. 获取非复权日K线数据
print("\n1. 获取非复权日K线数据...")

# "sh600000_from_baostock.csv"是从baostock下载到本地的日K线数据(时间：2014-01-01到2020-01-01)
# "sh600000_from_baostock.csv"包含如下数据：date,open,high,low,close,volume
baostock_file_path = "sh600000_from_baostock.csv"
kline_df = pd.read_csv(baostock_file_path)
print(f"获取到 {len(kline_df)} 条非复权日K线数据")

# 转换数据类型
kline_df["open"] = kline_df["open"].astype(float)
kline_df["high"] = kline_df["high"].astype(float)
kline_df["low"] = kline_df["low"].astype(float)
kline_df["close"] = kline_df["close"].astype(float)
kline_df["volume"] = kline_df["volume"].astype(float)
kline_df['date'] = pd.to_datetime(kline_df['date'])

# 2. 获取复权因子数据
print("\n2. 获取复权因子数据...")
# 注意：需要获取更早的复权因子，因为前复权需要用到整个历史区间的因子
factor_start = "2010-01-01"  # 扩大到2010年
factor_end = end_date

adjust_factor_data = bs.query_adjust_factor(
	stock_code,
	start_date=factor_start,
	end_date=factor_end
)

adjust_factor_df = adjust_factor_data.get_data()
print(f"获取到 {len(adjust_factor_df)} 条复权因子数据")
print(adjust_factor_df[['dividOperateDate', 'foreAdjustFactor']])

# 转换数据类型
adjust_factor_df['dividOperateDate'] = pd.to_datetime(adjust_factor_df['dividOperateDate'])
adjust_factor_df['foreAdjustFactor'] = adjust_factor_df['foreAdjustFactor'].astype(float)
adjust_factor_df = adjust_factor_df.sort_values('dividOperateDate')

# 3. 正确的复权计算方法
print("\n3. 计算前复权数据...")

# 创建复权因子查找函数
def get_factor_for_date(trade_date):
	"""
	查找小于等于交易日期的最接近的复权因子
	"""
	mask = adjust_factor_df['dividOperateDate'] <= trade_date
	if mask.any():
		return adjust_factor_df.loc[mask, 'foreAdjustFactor'].iloc[-1]
	else:
		# 如果没有找到，返回最新的复权因子（用于前复权）
		if not adjust_factor_df.empty:
			return adjust_factor_df['foreAdjustFactor'].iloc[-1]
		return 1.0

# 为每个交易日查找对应的复权因子
print("正在为每个交易日匹配复权因子...")
kline_df['adj_factor'] = kline_df['date'].apply(get_factor_for_date)

# 正确计算前复权数据：原始价格 / 复权因子
kline_df["adj_open"] = kline_df["open"] * kline_df["adj_factor"]
kline_df["adj_high"] = kline_df["high"] * kline_df["adj_factor"]
kline_df["adj_low"] = kline_df["low"] * kline_df["adj_factor"]
kline_df["adj_close"] = kline_df["close"] * kline_df["adj_factor"]

print("\n计算完成，复权后的数据：")
print(kline_df[['date', 'open', 'adj_open', 'close', 'adj_close', 'adj_factor']].head(10))

# 保存数据（可选）
kline_df.to_csv("sh600000_calculated.csv", index=False, float_format='%.6f')
print("\n数据已保存到CSV文件")

# 退出baostock
bs.logout()
```
