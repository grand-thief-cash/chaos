# BaoStock SDK 文档 · 分片 002

> 本分片包含第 11–20 份文档。导航：[返回总索引](index.md)。

## 本分片目录

11. [季频盈利能力](#baostock-document-011)
12. [季频营运能力](#baostock-document-012)
13. [季频成长能力](#baostock-document-013)
14. [季频偿债能力](#baostock-document-014)
15. [季频现金流量](#baostock-document-015)
16. [季频杜邦指数](#baostock-document-016)
17. [季频业绩快报](#baostock-document-017)
18. [季频业绩预告](#baostock-document-018)
19. [证券基本资料](#baostock-document-019)
20. [存款利率](#baostock-document-020)

---

<a id="baostock-document-011"></a>

## 11. 季频盈利能力

> 官方页面：[seasonProfit.md](https://baostock.com/mainContent?file=seasonProfit.md)


#### 季频盈利能力

##### 季频盈利能力：query_profit_data()

方法说明：通过API接口获取季频盈利能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。 

返回类型：pandas的DataFrame类型。 

使用示例 
    
  ```python
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

| code         | pubDate  | statDate  | roeAvg  | npMargin  | gpMargin  | netProfit  | epsTTM  | MBRevenue  | totalShare  | liqaShare   
--------------|---|---|---|---|---|---|---|---|---|---  
 sh.600000    | 2017-08-30  | 2017-06-30  | 0.074617  | 0.342179  |  | 28522000000.000000  | 1.939029  | 83354000000.000000  | 28103763899.00  | 28103763899.00   
 
返回数据说明

|参数名称 | 参数描述  | 算法说明   
 ---          |---|---  
 code         | 证券代码  |   
 pubDate      | 公司发布财报的日期  |   
 statDate     | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30  |   
 roeAvg       | 净资产收益率(平均)(%)  | 归属母公司股东净利润/[(期初归属母公司股东的权益+期末归属母公司股东的权益)/2]*100%   
 npMargin     | 销售净利率(%)  | 净利润/营业收入*100%   
 gpMargin     | 销售毛利率(%)  | 毛利/营业收入*100%=(营业收入-营业成本)/营业收入*100%   
 netProfit    | 净利润(元)  |   
 epsTTM       | 每股收益  | 归属母公司股东的净利润TTM/最新总股本   
 MBRevenue    | 主营营业收入(元)  |   
 totalShare   | 总股本  |   
 liqaShare    | 流通股本  |

---

<a id="baostock-document-012"></a>

## 12. 季频营运能力

> 官方页面：[seasonOperation.md](https://baostock.com/mainContent?file=seasonOperation.md)


#### 季频营运能力

##### 季频营运能力：query_operation_data()

方法说明：通过API接口获取季频营运能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。 

返回类型：pandas的DataFrame类型。 

使用示例 
    
  ```python
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

| code           | pubDate  | statDate  | NRTurnRatio  | NRTurnDays  | INVTurnRatio  | INVTurnDays  | CATurnRatio  | AssetTurnRatio   
----------------|---|---|---|---|---|---|---|---  
 sh.600000      | 2017-08-30  | 2017-06-30  |  |  |  |  |  | 0.014161   
 
返回数据说明 

| 参数名称   | 参数描述  | 算法说明   
 ---            |---|---  
 code           | 证券代码  |   
 pubDate        | 公司发布财报的日期  |   
 statDate       | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30  |   
 NRTurnRatio    | 应收账款周转率(次)  | 营业收入/[(期初应收票据及应收账款净额+期末应收票据及应收账款净额)/2]   
 NRTurnDays     | 应收账款周转天数(天)  | 季报天数/应收账款周转率(一季报：90天，中报：180天，三季报：270天，年报：360天)   
 INVTurnRatio   | 存货周转率(次)  | 营业成本/[(期初存货净额+期末存货净额)/2]   
 INVTurnDays    | 存货周转天数(天)  | 季报天数/存货周转率(一季报：90天，中报：180天，三季报：270天，年报：360天)   
 CATurnRatio    | 流动资产周转率(次)  | 营业总收入/[(期初流动资产+期末流动资产)/2]   
 AssetTurnRatio | 总资产周转率  | 营业总收入/[(期初资产总额+期末资产总额)/2]

---

<a id="baostock-document-013"></a>

## 13. 季频成长能力

> 官方页面：[seasonGrowth.md](https://baostock.com/mainContent?file=seasonGrowth.md)


#### 季频成长能力
##### 季频成长能力：query_growth_data()

方法说明：通过API接口获取季频成长能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。 返回类型：pandas的DataFrame类型。 使用示例 
    
  ```python
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

|code  | pubDate  | statDate  | YOYEquity  | YOYAsset  | YOYNI  | YOYEPSBasic  | YOYPNI   
---|---|---|---|---|---|---|---  
sh.600000  | 2017-08-30  | 2017-06-30  | 0.120243  | 0.101298  | 0.054808  | 0.021053  | 0.052111   

返回数据说明

| 参数名称        | 参数描述  | 算法说明   
-------------|---|---  
 code        | 证券代码  |   
 pubDate     | 公司发布财报的日期  |   
 statDate    | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30  |   
 YOYEquity   | 净资产同比增长率  | (本期净资产-上年同期净资产)/上年同期净资产的绝对值*100%   
 YOYAsset    | 总资产同比增长率  | (本期总资产-上年同期总资产)/上年同期总资产的绝对值*100%   
 YOYNI       | 净利润同比增长率  | (本期净利润-上年同期净利润)/上年同期净利润的绝对值*100%   
 YOYEPSBasic | 基本每股收益同比增长率  | (本期基本每股收益-上年同期基本每股收益)/上年同期基本每股收益的绝对值*100%   
 YOYPNI      | 归属母公司股东净利润同比增长率  | (本期归属母公司股东净利润-上年同期归属母公司股东净利润)/上年同期归属母公司股东净利润的绝对值*100%

---

<a id="baostock-document-014"></a>

## 14. 季频偿债能力

> 官方页面：[seasonBalance.md](https://baostock.com/mainContent?file=seasonBalance.md)


#### 季频偿债能力

##### 季频偿债能力：query_balance_data()

方法说明：通过API接口获取季频偿债能力信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。 返回类型：pandas的DataFrame类型。 使用示例 
    
  ```python
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

|code  | pubDate  | statDate  | currentRatio  | quickRatio  | cashRatio  | YOYLiability  | liabilityToAsset  | assetToEquity   
---|---|---|---|---|---|---|---|---  
sh.600000  | 2017-08-30  | 2017-06-30  |  |  |  | 0.100020  | 0.933703  | 15.083598   

返回数据说明

|参数名称  | 参数描述  | 算法说明   
---|---|---  
code  | 证券代码  |   
pubDate  | 公司发布财报的日期  |   
statDate  | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30  |   
currentRatio  | 流动比率  | 流动资产/流动负债   
quickRatio  | 速动比率  | (流动资产-存货净额)/流动负债   
cashRatio  | 现金比率  | (货币资金+交易性金融资产)/流动负债   
YOYLiability  | 总负债同比增长率  | (本期总负债-上年同期总负债)/上年同期中负债的绝对值*100%   
liabilityToAsset  | 资产负债率  | 负债总额/资产总额   
assetToEquity  | 权益乘数  | 资产总额/股东权益总额=1/(1-资产负债率)

---

<a id="baostock-document-015"></a>

## 15. 季频现金流量

> 官方页面：[seasonCashFlow.md](https://baostock.com/mainContent?file=seasonCashFlow.md)


#### 季频现金流量

##### 季频现金流量：query_cash_flow_data()

方法说明：通过API接口获取季频现金流量信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。 返回类型：pandas的DataFrame类型。 使用示例 
    
  ```python
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

| code                | pubDate  | statDate  | CAToAsset  | NCAToAsset  | tangibleAssetToAsset  | ebitToInterest  | CFOToOR  | CFOToNP  | CFOToGr   
---------------------|---|---|---|---|---|---|---|---|---  
 sh.600000           | 2017-08-30  | 2017-06-30  |  |  |  |  | —3.071550  | —8.976439  | —3.071550   

返回数据说明

|  参数名称         | 参数描述  | 算法说明   
 ---                 |---|---  
 code                | 证券代码  |   
 pubDate             | 公司发布财报的日期  |   
 statDate            | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30  |   
 CAToAsset           | 流动资产除以总资产  |   
 NCAToAsset          | 非流动资产除以总资产  |   
 tangibleAssetToAsset | 有形资产除以总资产  |   
 ebitToInterest      | 已获利息倍数  | 息税前利润/利息费用   
 CFOToOR             | 经营活动产生的现金流量净额除以营业收入  |   
 CFOToNP             | 经营性现金净流量除以净利润  |   
 CFOToGr             | 经营性现金净流量除以营业总收入  |

---

<a id="baostock-document-016"></a>

## 16. 季频杜邦指数

> 官方页面：[seasonDupont.md](https://baostock.com/mainContent?file=seasonDupont.md)


#### 季频杜邦指数

##### 季频杜邦指数：query_dupont_data()

方法说明：通过API接口获取季频杜邦指数信息，可以通过参数设置获取对应年份、季度数据，提供2007年至今数据。 返回类型：pandas的DataFrame类型。 使用示例 
    
  ```python
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

| code                 | pubDate  | statDate  | dupontROE  | dupontAssetStoEquity  | dupontAssetTurn  | dupontPnitoni   
----------------------|---|---|---|---|---|---  
 sh.600000            | 2017-08-30  | 2017-06-30  | 0.074617  | 15.594453  | 0.014161  | 0.987483   
 
返回示例数据  
 
| dupontNitogr | dupontTaxBurden  | dupontIntburden  | dupontEbittogr   
 --------------|---|---|---  
 0.342179     | 0.776088  |  |   
 
返回数据说明

|  参数名称         | 参数描述  | 算法说明   
 ---                  |---|---  
 code                 | 证券代码  |   
 pubDate              | 公司发布财报的日期  |   
 statDate             | 财报统计的季度的最后一天, 比如2017-03-31, 2017-06-30  |   
 dupontROE            | 净资产收益率  | 归属母公司股东净利润/[(期初归属母公司股东的权益+期末归属母公司股东的权益)/2]*100%   
 dupontAssetStoEquity | 权益乘数，反映企业财务杠杆效应强弱和财务风险  | 平均总资产/平均归属于母公司的股东权益   
 dupontAssetTurn      | 总资产周转率，反映企业资产管理效率的指标  | 营业总收入/[(期初资产总额+期末资产总额)/2]   
 dupontPnitoni        | 归属母公司股东的净利润/净利润，反映母公司控股子公司百分比。如果企业追加投资，扩大持股比例，则本指标会增加。  |   
 dupontNitogr         | 净利润/营业总收入，反映企业销售获利率  |   
 dupontTaxBurden      | 净利润/利润总额，反映企业税负水平，该比值高则税负较低。净利润/利润总额=1-所得税/利润总额  |   
 dupontIntburden      | 利润总额/息税前利润，反映企业利息负担，该比值高则税负较低。利润总额/息税前利润=1-利息费用/息税前利润   
 dupontEbittogr       | 息税前利润/营业总收入，反映企业经营利润率，是企业经营获得的可供全体投资人（股东和债权人）分配的盈利占企业全部营收收入的百分比  |

---

<a id="baostock-document-017"></a>

## 17. 季频业绩快报

> 官方页面：[seasonExpress.md](https://baostock.com/mainContent?file=seasonExpress.md)


#### 季频业绩快报

##### 季频公司业绩快报：query_performance_express_report()

方法说明：通过API接口获取季频公司业绩快报信息，可以通过参数设置获取起止年份数据，提供2006年至今数据。除几种特殊情况外，交易所未要求必须发布。 

返回类型：pandas的DataFrame类型。 

使用示例 
    
  ```python
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
  * start_date：开始日期，发布日期或更新日期在这个范围内；
  * end_date：结束日期，发布日期或更新日期在这个范围内。

返回示例数据 

| code                                | performanceExpPubDate  | performanceExpStatDate  | performanceExpUpdateDate  | performanceExpressTotalAsset  | performanceExpressNetAsset   
-------------------------------------|---|---|---|---|---  
 sh.600000                           | 2015-01-06  | 2014-12-31  | 2015-01-06  | 4195602000000.000000  | 260011000000.000000   
 sh.600000                           | 2016-01-05  | 2015-12-31  | 2016-01-05  | 5043060000000.000000  | 285245000000.000000   
 sh.600000                           | 2017-01-04  | 2016-12-31  | 2017-01-04  | 5857263000000.000000  | 338027000000.000000   
 
返回示例数据

 |performanceExpressEPSChgPct | performanceExpressROEWa  | performanceExpressEPSDiluted  | performanceExpressGRYOY  | performanceExpressOPYOY   
 ---                                 |---|---|---|---  
 0.326910                            | 21.020000  | 2.520000  | 0.228390  | 0.153803   
 0.191493                            | 18.820000  | 2.660000  | 0.192395  | 0.069764   
 0.115412                            | 16.350000  | 2.400000  | 0.097234  | 0.054384   

 返回数据说明
 
|参数名称                        | 参数描述   
 ---                                 |---  
 code                                | 证券代码   
 performanceExpPubDate               | 业绩快报披露日   
 performanceExpStatDate              | 业绩快报统计日期   
 performanceExpUpdateDate            | 业绩快报披露日(最新)   
 performanceExpressTotalAsset        | 业绩快报总资产   
 performanceExpressNetAsset          | 业绩快报净资产   
 performanceExpressEPSChgPct         | 业绩每股收益增长率   
 performanceExpressROEWa             | 业绩快报净资产收益率ROE-加权   
 performanceExpressEPSDiluted        | 业绩快报每股收益EPS-摊薄   
 performanceExpressGRYOY             | 业绩快报营业总收入同比   
 performanceExpressOPYOY             | 业绩快报营业利润同比

---

<a id="baostock-document-018"></a>

## 18. 季频业绩预告

> 官方页面：[seasonForecast.md](https://baostock.com/mainContent?file=seasonForecast.md)


#### 季频业绩预告

##### 季频公司业绩预告：query_forecast_report()

方法说明：通过API接口获取季频公司业绩预告信息，可以通过参数设置获取起止年份数据，提供2003年至今数据。除几种特殊情况外，交易所未要求必须发布。 

返回类型：pandas的DataFrame类型。 

使用示例 
    
  ```python
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
  * start_date：开始日期，发布日期或更新日期在这个范围内；
  * end_date：结束日期，发布日期或更新日期在这个范围内。

返回示例数据 

| code                          | profitForcastExpPubDate  | profitForcastExpStatDate  | profitForcastType  | profitForcastAbstract   
-------------------------------|---|---|---|---  
 sh.600000                     | 2010-01-05  | 2009-12-31  | 略增  | 预计2009年归属于上市公司股东净利润1319500万元，同比增长5.43%。   
 sh.600000                     | 2011-01-05  | 2010-12-31  | 略增  | 预计公司2010年年度归属于上市公司股东净利润为190.76亿元，较上年同期增长44.33％。   
 sh.600000                     | 2012-01-05  | 2011-12-31  | 略增  | 预计2011年1月1日至2011年12月31日，归属于上市公司股东的净利润：盈利272.36亿元，与上年同期相比增加了42.02%。   
 
返回示例数据  
 
| profitForcastChgPctUp    | profitForcastChgPctDwn   
 --------------------------|---  
 5.430000                 | 0.000000   
 44.330000                | 44.330000   
 42.020000                | 42.020000   
 
返回数据说明

|  参数名称                    | 参数描述   
 --------------------------|---  
 code                     | 证券代码   
 profitForcastExpPubDate  | 业绩预告发布日期   
 profitForcastExpStatDate | 业绩预告统计日期   
 profitForcastType        | 业绩预告类型   
 profitForcastAbstract    | 业绩预告摘要   
 profitForcastChgPctUp    | 预告归属于母公司的净利润增长上限(%)   
 profitForcastChgPctDwn   | 预告归属于母公司的净利润增长下限(%)

---

<a id="baostock-document-019"></a>

## 19. 证券基本资料

> 官方页面：[stockBasic.md](https://baostock.com/mainContent?file=stockBasic.md)


#### 证券基本资料

##### 证券基本资料：query_stock_basic()

方法说明：通过API接口获取证券基本资料，可以通过参数设置获取对应证券代码、证券名称的数据。 返回类型：pandas的DataFrame类型。 使用示例 
    
  ```python
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
  * code_name：股票名称，支持模糊查询，可以为空。
  * 当参数为空时，输出全部股票的基本信息。

返回示例数据

| code         | code_name  | ipoDate  | outDate  | type  | status   
--------------|---|---|---|---|---  
 sh.600000    | 浦发银行  | 1999-11-10  |  | 1  | 1   
 
返回数据说明 
 
| 参数名称      | 参数描述   
 -----------|---  
 code      | 证券代码   
 code_name | 证券名称   
 ipoDate   | 上市日期   
 outDate   | 退市日期   
 type      | 证券类型，其中1：股票，2：指数，3：其它，4：可转债，5：ETF   
 status    | 上市状态，其中1：上市，0：退市

---

<a id="baostock-document-020"></a>

## 20. 存款利率

> 官方页面：[depositRate.md](https://baostock.com/mainContent?file=depositRate.md)


#### 存款利率
##### 存款利率：query_deposit_rate_data()

方法说明：通过API接口获取存款利率，可以通过参数设置获取对应起止日期的数据。 返回类型：pandas的DataFrame类型。 使用示例 
    
```python    
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

  * start_date：开始日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空；
  * end_date：结束日期，格式XXXX-XX-XX，发布日期在这个范围内，可以为空。

返回示例数据 

| pubDate                          | demandDepositRate  | fixedDepositRate3Month  | fixedDepositRate6Month  | fixedDepositRate1Year  | fixedDepositRate2Year  | fixedDepositRate3Year   
----------------------------------|---|---|---|---|---|---  
 2015-03-01                       | 0.350000  | 2.100000  | 2.300000  | 2.500000  | 3.100000  | 3.750000   
 2015-05-11                       | 0.350000  | 1.850000  | 2.050000  | 2.250000  | 2.850000  | 3.500000   
 
返回示例数据 
 
| fixedDepositRate5Year            | installmentFixedDepositRate1Year  | installmentFixedDepositRate3Year  | installmentFixedDepositRate5Year   
 ----------------------------------|---|---|---  
| 2.100000                         | 2.300000  |   
| 1.850000                         | 2.050000  |   
 
返回数据说明
 
| 参数名称                             | 参数描述   
 ----------------------------------|---  
 pubDate                          | 发布日期   
 demandDepositRate                | 活期存款(不定期)   
 fixedDepositRate3Month           | 定期存款(三个月)   
 fixedDepositRate6Month           | 定期存款(半年)   
 fixedDepositRate1Year            | 定期存款整存整取(一年)   
 fixedDepositRate2Year            | 定期存款整存整取(二年)   
 fixedDepositRate3Year            | 定期存款整存整取(三年)   
 fixedDepositRate5Year            | 定期存款整存整取(五年)   
 installmentFixedDepositRate1Year | 零存整取、整存零取、存本取息定期存款(一年)   
 installmentFixedDepositRate3Year | 零存整取、整存零取、存本取息定期存款(三年)   
 installmentFixedDepositRate5Year | 零存整取、整存零取、存本取息定期存款(五年)
