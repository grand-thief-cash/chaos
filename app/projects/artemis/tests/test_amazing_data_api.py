# 第一步 登录api
import AmazingData as ad

#     username: "10100224503"
#     password: "10100224503@2026"
#     host: "101.230.159.234"
#     port: 8600

ad.login(username='10100224503', password='10100224503@2026',host='101.230.159.234',port=8600)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
industry_base_info = info_data_object.get_industry_base_info()
industry_base_list = list(industry_base_info['INDEX_CODE'])
# 行业指数成分股
industry_constituent = info_data_object.get_industry_constituent(industry_base_list, is_local=False)

print(industry_constituent)