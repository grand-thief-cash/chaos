from enum import Enum


class DataSource(str, Enum):
    DS_AMAZING_DATA = "amazing_data"
    DS_MAIRUI = "mairui"
    DS_BAOSTOCK = "baostock"
    DS_TUSHARE = "tushare"
    DS_EASTMONEY = "eastmoney"


class Taxonomy(str, Enum):
    """分类体系标识（独立于数据供应商）"""
    SWHY = "swhy"          # 申万宏源
    CITIC = "citic"        # 中信
    GICS = "gics"          # 全球行业分类标准
    CONCEPT = "concept"    # 概念板块
    REGION = "region"      # 地域板块
    MAIRUI = "mairui"      # 麦蕊分类

