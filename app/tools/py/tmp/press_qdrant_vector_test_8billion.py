import logging as logger
import os
import random

from locust import SequentialTaskSet, task, HttpUser, between, run_single_user, tag, stats
from urllib3.util import parse_url, Url
from utils.handle_file import HandleJson
from utils.log_util import LogUtil
from utils.utils import generate_normalized_vector

config = {
    "xindi": {
        "test_host": "https://qdrant-bpm-blue.rag-us.use1.dev-searchplatform.nl.lexis.com",
        "collection_dict": {
            "us_bpm": "us_bpm_0421",
            "us_jury_verdicts": "us_jury_verdicts_0421",
        }
    },
    "chaofan": {
        "test_host": "https://qdrant-cofi-secf-blue.rag-us.use1.dev-searchplatform.nl.lexis.com",
        "collection_dict": {
            "us_sec_filings": "us_sec_filings_0424",
            "us_expert_witness_summaries": "us_expert_witness_summaries_0422",
            "us_expert_witness_documents": "us_expert_witness_documents_0422",
            "us_expert_witness_profile": "us_expert_witness_profile_0422",
            "us_global_laws_regulations": "us_global_laws_regulations_0422",
            "us_jury_instruction_filings": "us_jury_instruction_filings_0422",
        }
    },
    "finn": {
        "test_host": "https://qdrant-cofi-blue.rag-us.use1.dev-searchplatform.nl.lexis.com",
        "collection_dict": {
            "us_analyst_reports": "us_analyst_reports_20260421",
            "us_mergers_and_acquisitions": "us_mergers_and_acquisitions_20260421",
        }
    },
    "holiday": {
        "test_host": "https://qdrant-exp-green.rag-us.use1.dev-searchplatform.nl.lexis.com",
        "collection_dict": {
            "us_expert_witness_documents": "us_expert_witness_documents_0422",
            "us_expert_witness_profile": "us_expert_witness_profile_0422",
            "us_global_laws_regulations": "us_global_laws_regulations_0422",
            "us_jury_instruction_filings": "us_jury_instruction_filings_0422",
        }
    },
    "eileen": {
        "test_host": "https://qdrant-am-blue.rag-us.use1.dev-searchplatform.nl.lexis.com",
        "collection_dict": {
            "us_citators": "us_citators_20260420",
            "us_practice_insights": "us_practice_insights_20260420",
            "us_legal_topic_summaries": "us_legal_topic_summaries_20260420",
            "us_law_reviews_and_journals": "us_law_reviews_and_journals_20260420",
            "us_jurisprudence": "us_jurisprudence_20260420",
            "us_jurisdictional_surveys": "us_jurisdictional_surveys_20260420",
            "us_emerging_issues_analysis": "us_emerging_issues_analysis_20260420",
            "us_cle_course_of_study_materials": "us_cle_course_of_study_materials_20260420",
        }
    },
    "xiaoyi": {
        "test_host": "https://qdrant-am-blue.rag-us.use1.dev-searchplatform.nl.lexis.com",
        "collection_dict": {
            "us_medical_references": "us_medical_references_20260420",
            "us_scientific_publications": "us_scientific_publications_20260427",
        }
    },
}
# stats.CONSOLE_STATS_INTERVAL_SEC = 10 # 控制台日志输出间隔时间，默认2秒
log_print_req_resp_record = 0

env = os.environ.get("env")
logger.info("准备压测的环境：" + env)

if env not in config:
    raise ValueError(f"环境标识传参错误! 目前传参环境标识{env} 应传参 {' '.join(config.keys())}")

test_host = config[env]["test_host"]
collection_dict = config[env].get("collection_dict", {})

weight = {
    "us_bpm": 1,
    "us_sec_filings": 1,
    "us_analyst_reports": 1,
    "us_mergers_and_acquisitions": 1,
    "us_jury_verdicts": 1,
    "us_expert_witness_documents": 1,
    "us_expert_witness_profile": 1,
    "us_expert_witness_summaries": 1,
    "us_global_laws_regulations": 1,
    "us_jury_instruction_filings": 1,
    "us_citators": 1,
    "us_practice_insights": 1,
    "us_legal_topic_summaries": 1,
    "us_law_reviews_and_journals": 1,
    "us_jurisprudence": 1,
    "us_jurisdictional_surveys": 1,
    "us_emerging_issues_analysis": 1,
    "us_cle_course_of_study_materials": 1,
    "us_medical_references": 1,
    "us_scientific_publications": 1,
}


us_bpm_pcsi_list = HandleJson.get_value(os.path.join("data", "qdrant", "us_bpm_pcsi_list.json"))
us_law_reviews_and_journals_pcsi_list = HandleJson.get_value(os.path.join("data", "qdrant", "us_law_reviews_and_journals_pcsi_list.json"))

parsed_url: Url = parse_url(test_host)
host_alais = parsed_url.host.split(".")[0]

class WebsiteUser(HttpUser):
    host = test_host
    # wait_time = between(0.1, 0.5)

    def real_request(self, url, data, tag=None):
        params = {
            "timeout": 10,
            # "consistency": "majority",
        }
        with self.client.post(url, json=data, params=params, name=f"{host_alais} {url}", catch_response=True) as response:
            if response.status_code not in [200, 206]:
                if response.status_code == 0:
                    response.failure("RequestException")
                else:
                    response.failure("status_code error")
                    LogUtil.get_http_req_resp_record(response)
            else:
                try:
                    result = response.json()
                    status = result.get("status")
                    if status != "ok":
                        response.failure("status is not ok")
                        LogUtil.get_http_req_resp_record(response)
                    else:
                        self.special_handle_response(data, result, response, tag)
                        if log_print_req_resp_record:
                            i = random.randint(0, 50000)
                            if i == 5:
                                LogUtil.get_http_req_resp_record(response)
                except ValueError:
                    response.failure("Response content is not valid JSON")
                    LogUtil.get_http_req_resp_record(response)
                except Exception as e:
                    response.failure(f"error: {e}")
                    LogUtil.get_http_req_resp_record(response)

    def special_handle_response(self, data, result, response, tag:str=None):
        if tag is None:
            return
        if "sparse" in tag:
            o_passage_text = data["query"]["text"]
            points = result["result"]["points"]
            if points:
                p = points[0]
                r_passage_text = p["payload"]["passage_text"]
                if o_passage_text not in r_passage_text:
                    response.failure("passage_text not match")
                    LogUtil.get_http_req_resp_record(response)

    def real_request_query(self, collection, data, tag=None):
        real_collection = collection_dict.get(collection, collection)
        url = f'/collections/{real_collection}/points/query'
        self.real_request(url, data, tag)

    def real_request_scroll(self, collection, data, tag=None):
        real_collection = collection_dict.get(collection, collection)
        url = f'/collections/{real_collection}/points/scroll'
        self.real_request(url, data, tag)

    def get_request_data_us_bpm_01(self):
        passage_vector = generate_normalized_vector()
        data = {
            "query": passage_vector,
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {"key": "filed_date", "range": {"gte": "1900-01-01T00:00:00Z", "lte": "2025-12-31T23:59:59Z"}},
                    {"key": "pcsi", "match": {"any": us_bpm_pcsi_list}},
                    {"key": "word_count", "range": {"gte": 50, "lte": 350}},
                ]
            },
            "with_payload": ["passage_id", "lni", "short_case_name"],
            "with_vector": False
        }
        return data

    @tag("us_bpm")
    @task(weight["us_bpm"])
    def press_us_bpm(self):
        data = self.get_request_data_us_bpm_01()
        self.real_request_query("us_bpm", data, tag="us_bpm")

    def get_request_data_us_jury_verdicts_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "publish_date",
                        "range": {
                            "gte": "1990-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    },
                    {
                        "key": "word_count",
                        "range": {
                            "gte": 50,
                            "lte": 350
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                485454,
                                485454,
                                30339,
                                30348,
                                30380
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_jury_verdicts")
    @task(weight["us_jury_verdicts"])
    def press_us_jury_verdicts(self):
        data = self.get_request_data_us_jury_verdicts_01()
        self.real_request_query("us_jury_verdicts", data, tag="us_jury_verdicts")

    def get_request_data_us_sec_filings_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "geography_guid",
                        "match": {
                            "any": [
                                "urn:entity:geob-102975340",
                                "urn:entity:geob-103052329",
                                "urn:entity:geob-102953012",
                                "urn:entity:geob-102921261"
                            ]
                        }
                    },
                    {
                        "key": "pub_name",
                        "match": {
                            "any": [
                                "SEC EDGAR Filings, Combined"
                            ]
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                435927,
                                435880
                            ]
                        }
                    }
                ],
                "must_not": [
                    {
                        "is_empty": {
                            "key": "title"
                        }
                    },
                    {
                        "is_null": {
                            "key": "title"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_sec_filings")
    @task(weight["us_sec_filings"])
    def press_us_sec_filings(self):
        data = self.get_request_data_us_sec_filings_01()
        self.real_request_query("us_sec_filings", data, tag="us_sec_filings")

    def get_request_data_us_analyst_reports_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "date",
                        "range": {
                            "gte": "1900-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    },
                    {
                        "key": "publication_type",
                         "match": {
                            "any": [
                                "Analyst Report",
                                "Stock Report",
                            ]
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                404527,
                                237542,
                                443221,
                                411802,
                                373064,
                                263807,
                                247512,
                                323057,
                                373788,
                                373786,
                                322877,
                                418977,
                                373757,
                                3720,
                                373781,
                                373765,
                                373763,
                                373808,
                                348345,
                                296262,
                                427515,
                                373792,
                                436651,
                                373821,
                                424357,
                                399898,
                                373827,
                                373807,
                                373809,
                                401636,
                                373759,
                                401640,
                                401642,
                                373811,
                                373744,
                                570155,
                                373761,
                                426677,
                                401638,
                                373733,
                                373777,
                                373778,
                                426666,
                                426672,
                                373775,
                                3721,
                                373810,
                                411492,
                                426671,
                                426674,
                                464630,
                                465677,
                                426669,
                                439370,
                                571594,
                                439354,
                                439365,
                                439369,
                                439367,
                                439371,
                                439368,
                                475926,
                                571714,
                                439372,
                                439366,
                                426675,
                                427330,
                                405461,
                                471345,
                                475979,
                                475982
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_analyst_reports")
    @task(weight["us_analyst_reports"])
    def press_us_analyst_reports(self):
        data = self.get_request_data_us_analyst_reports_01()
        self.real_request_query("us_analyst_reports", data, tag="us_analyst_reports")

    def get_request_data_us_mergers_and_acquisitions_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "date",
                        "range": {
                            "gte": "1900-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                488312,
                                477262,
                                386009,
                                173725,
                                156282,
                                430765,
                                429051,
                                211789,
                                281887,
                                437501,
                                400616,
                                471348
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_mergers_and_acquisitions")
    @task(weight["us_mergers_and_acquisitions"])
    def press_us_mergers_and_acquisitions(self):
        data = self.get_request_data_us_mergers_and_acquisitions_01()
        self.real_request_query("us_mergers_and_acquisitions", data, tag="us_mergers_and_acquisitions")

    def get_request_data_us_expert_witness_documents_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "date",
                        "range": {
                            "gte": "1996-01-01T00:00:00Z"
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                157181,
                                322632,
                                322643,
                                343894,
                                369559,
                                369562,
                                371464,
                                371465,
                                605427,
                                605428,
                                605429,
                                605464
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_expert_witness_documents")
    @task(weight["us_expert_witness_documents"])
    def press_us_expert_witness_documents(self):
        data = self.get_request_data_us_expert_witness_documents_01()
        self.real_request_query("us_expert_witness_documents", data, tag="us_expert_witness_documents")

    def get_request_data_us_expert_witness_profile_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                368258,
                                371209,
                                371210,
                                376245
                            ]
                        }
                    }
                ]
            },
            "limit": 10,
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_expert_witness_profile")
    @task(weight["us_expert_witness_profile"])
    def press_us_expert_witness_profile(self):
        data = self.get_request_data_us_expert_witness_profile_01()
        self.real_request_query("us_expert_witness_profile", data, tag="us_expert_witness_profile")

    def get_request_data_us_expert_witness_summaries_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                305264
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_expert_witness_summaries")
    @task(weight["us_expert_witness_summaries"])
    def press_us_expert_witness_summaries(self):
        data = self.get_request_data_us_expert_witness_summaries_01()
        self.real_request_query("us_expert_witness_summaries", data, tag="us_expert_witness_summaries")

    def get_request_data_us_global_laws_regulations_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "date",
                        "range": {
                            "gte": "1996-01-01T00:00:00Z"
                        }
                    },
                    {
                        "key": "publication",
                        "match": {
                            "any": [
                                "Global-Regulation - Luxembourg",
                                "UNDEFINED"
                            ]
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                472336, 472337, 472338, 472339, 472340, 474667, 474668, 474669, 474670, 474671, 
                                474672, 474673, 474675, 474676, 474703, 475231, 475232, 475233, 475234, 475235, 
                                475236, 475237, 475238, 475239, 475240, 475241, 475242, 475243, 475244, 475245, 
                                475246, 475247, 475249, 475250, 477198, 573974
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_global_laws_regulations")
    @task(weight["us_global_laws_regulations"])
    def press_us_global_laws_regulations(self):
        data = self.get_request_data_us_global_laws_regulations_01()
        self.real_request_query("us_global_laws_regulations", data, tag="us_global_laws_regulations")

    def get_request_data_us_jury_instruction_filings_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 10,
            "filter": {
                "must": [
                    {
                        "key": "date",
                        "range": {
                            "gte": "1996-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    },
                    {
                        "key": "court_guid",
                        "match": {
                            "any": [
                                "urn:entity:jb-100000391",
                                "urn:entity:jb-100005259",
                                "urn:entity:jb-100000101",
                                "urn:entity:jb-100000420"
                            ]
                        }
                    },
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                296724, 296737, 296756, 309717, 351947, 351948, 351949, 351950, 351951, 351952, 
                                351953, 351954, 351955, 351956, 351957, 351958, 351959, 351960, 351961, 351962
                            ]
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni"
            ],
            "with_vector": False
        }
        return data

    @tag("us_jury_instruction_filings")
    @task(weight["us_jury_instruction_filings"])
    def press_us_jury_instruction_filings(self):
        data = self.get_request_data_us_jury_instruction_filings_01()
        self.real_request_query("us_jury_instruction_filings", data, tag="us_jury_instruction_filings")

    def get_request_data_us_citators_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                12235,
                                12236,
                                12237,
                                12238,
                                12239,
                                12240,
                                12241,
                                12242,
                                12243,
                                12244,
                                160922,
                                161722,
                                161728,
                                161734,
                                164448,
                                167176,
                                167180,
                                168837,
                                240557,
                                240560,
                                247604,
                                250587,
                                258573,
                                380044,
                                402015,
                                410583,
                                426236,
                                430703,
                                443348,
                                443349,
                                475222,
                                475226,
                                475227,
                                477621,
                                482106,
                                482641,
                                483478,
                                483480,
                                486598,
                                486601,
                                487663,
                                489575
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "editorial_summary",
                                "body_text",
                                "footnote"
                            ]
                        }
                    },
                    {
                        "key": "decision_date",
                        "range": {
                            "gte": "1900-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "title",
                "case_name"
            ],
            "with_vector": False
        }
        return data

    @tag("us_citators")
    @task(weight["us_citators"])
    def press_us_citators(self):
        data = self.get_request_data_us_citators_01()
        self.real_request_query("us_citators", data, tag="us_citators")

    def get_request_data_us_practice_insights_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                297318,
                                297319,
                                297320,
                                297321,
                                297322,
                                297323,
                                297324,
                                297325,
                                297326,
                                297327,
                                297328,
                                297329,
                                297330,
                                297331,
                                297332,
                                297333,
                                297334,
                                297335,
                                297336,
                                297337,
                                297338,
                                297339,
                                297340,
                                297341,
                                297342,
                                297343,
                                297344,
                                297345,
                                297346,
                                297347,
                                297348,
                                297349,
                                297350,
                                297351,
                                297352,
                                297353,
                                297355,
                                297357,
                                297358,
                                297359,
                                297360,
                                297361,
                                297362,
                                297363,
                                297364,
                                297365,
                                297366,
                                297367,
                                297368,
                                297369,
                                297370
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "body",
                                "bio",
                                "section",
                                "footnote"
                            ]
                        }
                    }
                ],
                "must_not": [
                    {
                        "is_empty": {
                            "key": "core_terms"
                        }
                    },
                    {
                        "is_null": {
                            "key": "core_terms"
                        }
                    },
                    {
                        "is_empty": {
                            "key": "core_phrases"
                        }
                    },
                    {
                        "is_null": {
                            "key": "core_phrases"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "title"
            ],
            "with_vector": False
        }
        return data

    @tag("us_practice_insights")
    @task(weight["us_practice_insights"])
    def press_us_practice_insights(self):
        data = self.get_request_data_us_practice_insights_01()
        self.real_request_query("us_practice_insights", data, tag="us_practice_insights")

    def get_request_data_us_legal_topic_summaries_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                4336
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "body",
                                "definition"
                            ]
                        }
                    },
                    {
                        "should": [
                            {
                                "is_empty": {
                                    "key": "core_terms"
                                }
                            },
                            {
                                "is_null": {
                                    "key": "core_terms"
                                }
                            }
                        ]
                    },
                    {
                        "should": [
                            {
                                "is_empty": {
                                    "key": "core_phrases"
                                }
                            },
                            {
                                "is_null": {
                                    "key": "core_phrases"
                                }
                            }
                        ]
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "passage_type"
            ],
            "with_vector": False
        }
        return data

    @tag("us_legal_topic_summaries")
    @task(weight["us_legal_topic_summaries"])
    def press_us_legal_topic_summaries(self):
        data = self.get_request_data_us_legal_topic_summaries_01()
        self.real_request_query("us_legal_topic_summaries", data, tag="us_legal_topic_summaries")

    def get_request_data_us_law_reviews_and_journals_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": us_law_reviews_and_journals_pcsi_list
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "body",
                                "footnote"
                            ]
                        }
                    },
                    {
                        "key": "publication_date",
                        "range": {
                            "gte": "1900-01-01T00:00:00Z",
                            "lte": "2026-12-31T23:59:59Z"
                        }
                    },
                    {
                        "key": "length",
                        "range": {
                            "gte": 100,
                            "lte": 30000
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "title"
            ],
            "with_vector": False
        }
        return data

    @tag("us_law_reviews_and_journals")
    @task(weight["us_law_reviews_and_journals"])
    def press_us_law_reviews_and_journals(self):
        data = self.get_request_data_us_law_reviews_and_journals_01()
        self.real_request_query("us_law_reviews_and_journals", data, tag="us_law_reviews_and_journals")

    def get_request_data_us_jurisprudence_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                148106,
                                153083,
                                162586,
                                162589,
                                172851,
                                174618,
                                222615,
                                230199,
                                253746,
                                338593,
                                338594,
                                338595,
                                338596,
                                338920,
                                345867,
                                346222,
                                494806
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "section",
                                "footnote"
                            ]
                        }
                    }
                ],
                "must_not": [
                    {
                        "is_empty": {
                            "key": "core_terms"
                        }
                    },
                    {
                        "is_null": {
                            "key": "core_terms"
                        }
                    },
                    {
                        "is_empty": {
                            "key": "core_phrases"
                        }
                    },
                    {
                        "is_null": {
                            "key": "core_phrases"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "title"
            ],
            "with_vector": False
        }
        return data

    @tag("us_jurisprudence")
    @task(weight["us_jurisprudence"])
    def press_us_jurisprudence(self):
        data = self.get_request_data_us_jurisprudence_01()
        self.real_request_query("us_jurisprudence", data, tag="us_jurisprudence")

    def get_request_data_us_jurisdictional_surveys_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                312472,
                                312774
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "body",
                                "footnote",
                                "table"
                            ]
                        }
                    },
                    {
                        "key": "publication_date",
                        "range": {
                            "gte": "2010-01-01T00:00:00Z",
                            "lte": "2026-12-31T23:59:59Z"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "title"
            ],
            "with_vector": False
        }
        return data

    @tag("us_jurisdictional_surveys")
    @task(weight["us_jurisdictional_surveys"])
    def press_us_jurisdictional_surveys(self):
        data = self.get_request_data_us_jurisdictional_surveys_01()
        self.real_request_query("us_jurisdictional_surveys", data, tag="us_jurisdictional_surveys")

    def get_request_data_us_emerging_issues_analysis_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                122100,
                                319616,
                                319622,
                                319626,
                                322297,
                                322300,
                                322709,
                                326167,
                                327770,
                                339086,
                                341511,
                                341517,
                                341520,
                                341524,
                                341525,
                                341563,
                                341566,
                                344545,
                                345643,
                                352080,
                                352081,
                                352082,
                                352083,
                                352086,
                                352087,
                                352089,
                                352091,
                                352092,
                                352094,
                                352095,
                                352096,
                                352097,
                                352098,
                                352100,
                                352101,
                                352103,
                                352105,
                                352106,
                                352107,
                                352108,
                                352110,
                                352111,
                                352112,
                                352114,
                                352115,
                                389875
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "abstract",
                                "author_bio",
                                "body",
                                "footnote"
                            ]
                        }
                    },
                    {
                        "key": "publication_date",
                        "range": {
                            "gte": "2010-01-01T00:00:00Z",
                            "lte": "2026-12-31T23:59:59Z"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "passage_type"
            ],
            "with_vector": False
        }
        return data

    @tag("us_emerging_issues_analysis")
    @task(weight["us_emerging_issues_analysis"])
    def press_us_emerging_issues_analysis(self):
        data = self.get_request_data_us_emerging_issues_analysis_01()
        self.real_request_query("us_emerging_issues_analysis", data, tag="us_emerging_issues_analysis")

    def get_request_data_us_cle_course_of_study_materials_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": False,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                154359, 154362, 154364, 154365, 154366, 154367, 154368, 154369, 154370, 154371,
                                154374, 154375, 154376, 154377, 154379, 154380, 156200, 156201, 156202, 156203,
                                156204, 156205, 156206, 156207, 156209, 156211, 156212, 166155, 166156, 166158,
                                166159, 166160, 166161, 166162, 166163, 166165, 166168, 166177, 166178, 166180,
                                166182, 166183, 166184, 166185, 166187, 166189, 166190, 166195, 220800, 220820,
                                220826, 220833, 220853, 220856, 220860, 220884, 221133, 221148, 221150, 221152,
                                221516, 221521, 221566, 221572, 237316, 237317, 237318, 237689, 239301, 239302,
                                239303, 242119, 242121, 244432, 250727, 250729, 250730, 250731, 290866
                            ]
                        }
                    },
                    {
                        "key": "passage_type",
                        "match": {
                            "any": [
                                "section",
                                "footnote"
                            ]
                        }
                    }
                ],
                "must_not": [
                    {
                        "is_empty": {
                            "key": "core_terms"
                        }
                    },
                    {
                        "is_null": {
                            "key": "core_terms"
                        }
                    },
                    {
                        "is_empty": {
                            "key": "core_phrases"
                        }
                    },
                    {
                        "is_null": {
                            "key": "core_phrases"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
                "passage_type"
            ],
            "with_vector": False
        }
        return data

    @tag("us_cle_course_of_study_materials")
    @task(weight["us_cle_course_of_study_materials"])
    def press_us_cle_course_of_study_materials(self):
        data = self.get_request_data_us_cle_course_of_study_materials_01()
        self.real_request_query("us_cle_course_of_study_materials", data, tag="us_cle_course_of_study_materials")

    def get_request_data_us_medical_references_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                11907,
                                11908,
                                11909,
                                142451,
                                142452,
                                160563,
                                232285,
                                232288,
                                262126,
                                313019
                            ]
                        }
                    },
                    {
                        "key": "publication_date",
                        "range": {
                            "gte": "2000-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi"
            ],
            "with_vector": False
        }
        return data

    @tag("us_medical_references")
    @task(weight["us_medical_references"])
    def press_us_medical_references(self):
        data = self.get_request_data_us_medical_references_01()
        self.real_request_query("us_medical_references", data, tag="us_medical_references")

    def get_request_data_us_scientific_publications_01(self):
        data = {
            "query": generate_normalized_vector(),
            "using": "passage_vector",
            "params": {
                "hnsw_ef": 48,
                "exact": False,
                "quantization": {
                    "ignore": False,
                    "rescore": True,
                    "oversampling": 2
                }
            },
            "limit": 60,
            "filter": {
                "must": [
                    {
                        "key": "pcsi",
                        "match": {
                            "any": [
                                154080,
                                301530,
                                301531,
                                301606,
                                301607,
                                301608,
                                301609,
                                301610
                            ]
                        }
                    },
                    {
                        "key": "publication_type",
                        "match": {
                            "any": [
                                "Journal"
                            ]
                        }
                    },
                    {
                        "key": "publication_date",
                        "range": {
                            "gte": "1990-01-01T00:00:00Z",
                            "lte": "2025-12-31T23:59:59Z"
                        }
                    }
                ]
            },
            "with_payload": [
                "passage_id",
                "lni",
                "pcsi",
            ],
            "with_vector": False
        }
        return data

    @tag("us_scientific_publications")
    @task(weight["us_scientific_publications"])
    def press_us_scientific_publications(self):
        data = self.get_request_data_us_scientific_publications_01()
        self.real_request_query("us_scientific_publications", data, tag="us_scientific_publications")

if __name__ == '__main__':
    run_single_user(WebsiteUser)

