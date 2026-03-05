"""高德地图服务封装 - 使用 HTTP API"""

from typing import List, Dict, Any, Optional
import httpx
import json
from ..config import get_settings
from ..models.schemas import Location, POIInfo, WeatherInfo


class AmapService:
    """高德地图服务封装类 - 使用 HTTP API"""

    def __init__(self):
        """初始化服务"""
        self.settings = get_settings()
        if not self.settings.amap_api_key:
            raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")

        self.api_key = self.settings.amap_api_key
        self.base_url = "https://restapi.amap.com/v3"
    
    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[Dict[str, Any]]:
        """
        搜索POI - 使用高德地图 HTTP API

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表
        """
        try:
            url = f"{self.base_url}/place/text"
            params = {
                "key": self.api_key,
                "keywords": keywords,
                "city": city,
                "citylimit": "true" if citylimit else "false",
                "offset": 20,  # 返回20个结果
                "extensions": "all"  # 返回详细信息
            }

            response = httpx.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("pois"):
                print(f"✅ 搜索到 {len(data['pois'])} 个POI: {keywords} @ {city}")
                return data["pois"]
            else:
                print(f"⚠️  未搜索到POI: {keywords} @ {city}")
                return []

        except Exception as e:
            print(f"❌ POI搜索失败: {str(e)}")
            return []
    
    def get_weather(self, city: str) -> Dict[str, Any]:
        """
        查询天气 - 使用高德地图 HTTP API

        Args:
            city: 城市名称或城市编码(adcode)

        Returns:
            天气信息字典
        """
        try:
            url = f"{self.base_url}/weather/weatherInfo"
            params = {
                "key": self.api_key,
                "city": city,
                "extensions": "all"  # 返回预报天气
            }

            response = httpx.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("forecasts"):
                forecast = data["forecasts"][0] if data["forecasts"] else {}
                print(f"✅ 获取天气成功: {city}")
                return forecast
            else:
                print(f"⚠️  未获取到天气: {city}")
                return {}

        except Exception as e:
            print(f"❌ 天气查询失败: {str(e)}")
            return {}
    


# 创建全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service
    
    if _amap_service is None:
        _amap_service = AmapService()
    
    return _amap_service

