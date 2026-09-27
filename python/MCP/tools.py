import requests
from fastmcp import FastMCP, Context
from pydantic import BaseModel,Field
PRE_URL = "http://localhost:8080/"

class InboundProduct(BaseModel):
    """批量进货接口的商品类"""
    product_id: int = Field(description="商品ID")
    quantity: int = Field(description="进货的商品数量（必须为正数）")

#访问Java后端的tool需要提取token鉴权
def getToken(ctx:Context = None):
    if ctx is None:
        return None
    meta = ctx.request_context.meta
    authorization_token = None
    if meta:
        authorization_token = meta.authorization
    return authorization_token

def register_tools(mcp: FastMCP):
    @mcp.tool()
    def get_store_sales_performance(store_code: str,begin_time: str|None = None,end_time: str|None = None,ctx:Context = None):
        """
        根据门店编号获取门店在某个时间段内的销售情况
        :param store_code: 门店编号
        :param begin_time: 查询的开始时间
        :param end_time: 查询的截止时间
        :return: 销售情况或错误通知
        """
        url = PRE_URL + "stores/sales/performance/" + store_code
        params = {}
        if begin_time:
            params["begin_time"] = begin_time
        if end_time:
            params["end_time"] = end_time
        result = requests.get(
            url,
            params=params,
            headers={
                "Accept": "application/json",
                "Authorization": getToken(ctx)
            }
        )
        data = result.json()
        if data["code"] == 200:
            return data["data"]
        else:
            return data["message"]

    @mcp.tool()
    def get_store_inventory(store_code: str,ctx:Context = None):
        """
        根据门店编号获取门店的库存情况
        :param store_code: 门店编号
        :return: 库存信息或者错误消息
        """
        url = PRE_URL + "stores/inventory/" + store_code
        result = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": getToken(ctx)
            }
        )
        data = result.json()
        if data["code"] == 200:
            return data["data"]
        else:
            return data["message"]


    @mcp.tool()
    def store_inbound(store_id: int,product_list: list[InboundProduct],ctx:Context = None):
        """
        :param store_id: 进货的门店ID
        :param product_list: 需要进货的商品列表
        :return: 进货成功提示或者错误信息
        """
        url = PRE_URL + "inventory/inbound"
        result = requests.post(
            url=url,
            headers={
                "Accept": "application/json",
                "Authorization": getToken(ctx)
            },
            json={
                "storeId": store_id,
                "productList": [
                    {
                        "productId": product.product_id,
                        "quantity": product.quantity,
                    }
                    for product in product_list
                ],
                "recordChangeType": 0
            }
        )
        data = result.json()
        return data["message"]

    @mcp.tool()
    def conditional_search_stores(page_num: int = 1,province: str = None,city: str = None,
                                             district: str = None,ctx:Context = None):
        """
        分页查询符合条件的门店信息
        :param page_num: 查询的第几页
        :param province: 查询的门店所在的省份
        :param city: 查询的门店所在的市
        :param district: 查询的门店所在的区
        :return: 门店的信息
        """
        url = PRE_URL + "stores/list"
        result = requests.get(
            url,
            params={
                "pageNum": page_num, "province": province,"city": city,"district": district
            },
            headers = {
                "Accept": "application/json",
                "Authorization": getToken(ctx)
            }
        )
        data = result.json()
        if data["code"] == 200:
            return data["data"]
        else:
            return data["message"]

    @mcp.tool()
    def check_product_list(category_id: int = 0,page_num: int = 1,ctx:Context = None):
        """
        分页查询可供进货的商品
        :param category_id: 商品种类 0-无条件全查，1-饮料，2-零食，3-日用品，4-粮油，5-家具，6-化妆品，7-服装，8-其他
        :param page_num: 查询的第几页
        :return: 商品信息或者错误信息
        """
        url = PRE_URL + "products/list"
        result = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": getToken(ctx)
            },
            json={
                "categoryId": category_id,
                "pageNum": page_num,
            }
        )
        data = result.json()
        if data["code"] == 200:
            return data["data"]
        else:
            return data["message"]


