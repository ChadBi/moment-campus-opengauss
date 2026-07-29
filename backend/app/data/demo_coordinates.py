"""Three-school demo coordinate catalog.

All coordinates use GCJ-02, matching the AMap raster base map. Records marked
``amap_poi`` come from an unambiguous AMap place entry; generic demo locations
without a unique public POI are deliberately marked ``demo_approximate``.
"""
from typing import Literal, TypedDict


COORDINATE_SYSTEM = "GCJ-02"


class DemoLocation(TypedDict):
    name: str
    latitude: float
    longitude: float
    description: str
    quality: Literal["amap_poi", "demo_approximate"]
    source: str


class DemoSchoolCoordinates(TypedDict):
    center_lat: float
    center_lng: float
    bounds: tuple[float, float, float, float]
    center_quality: Literal["amap_poi", "demo_approximate"]
    center_source: str
    locations: list[DemoLocation]


def _location(
    name: str,
    latitude: float,
    longitude: float,
    description: str,
    *,
    quality: Literal["amap_poi", "demo_approximate"] = "demo_approximate",
    source: str = "高德底图人工校准（演示落点）",
) -> DemoLocation:
    return {
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "description": description,
        "quality": quality,
        "source": source,
    }


DEMO_SCHOOL_COORDINATES: dict[str, DemoSchoolCoordinates] = {
    "jiangnan": {
        "center_lat": 31.483652,
        "center_lng": 120.271160,
        "bounds": (31.4740, 31.4920, 120.2580, 120.2800),
        "center_quality": "amap_poi",
        "center_source": "https://ditu.amap.com/place/B01FE0I99I",
        "locations": [
            _location("北门", 31.490227, 120.269806, "蠡湖大道北侧入口"),
            _location(
                "南门", 31.474719, 120.272855, "校园南入口",
                quality="amap_poi", source="https://ditu.amap.com/place/B01FE0IFB6",
            ),
            _location("第一食堂", 31.484820, 120.266820, "主食堂"),
            _location("第二食堂", 31.479920, 120.275560, "学生食堂"),
            _location("图书馆", 31.480930, 120.270080, "主图书馆"),
            _location("体育馆", 31.486660, 120.276420, "综合体育馆"),
            _location("田径场", 31.487180, 120.277560, "主田径场"),
            _location("教学楼A区", 31.484180, 120.272180, "主要教学区"),
            _location("学士公寓", 31.477760, 120.276520, "学生宿舍区"),
            _location("校园超市", 31.478620, 120.275180, "综合超市"),
            _location("文浩科学馆", 31.481880, 120.266420, "讲座演出场地"),
            _location("大学生活动中心", 31.478880, 120.268420, "社团活动场地"),
            _location("蠡湖畔", 31.482020, 120.271820, "校园水域景观"),
            _location("快递服务中心", 31.476820, 120.267880, "校园快递点"),
            _location("打印文印店", 31.483860, 120.273520, "文印服务"),
        ],
    },
    "fudan": {
        "center_lat": 31.297920,
        "center_lng": 121.503540,
        "bounds": (31.2905, 31.3020, 121.4970, 121.5105),
        "center_quality": "demo_approximate",
        "center_source": "高德底图邯郸校区本部与南区覆盖范围中心",
        "locations": [
            _location(
                "邯郸路校门", 31.300512, 121.507121, "邯郸路主入口",
                quality="amap_poi", source="https://ditu.amap.com/place/B00155K7SK",
            ),
            _location(
                "南区校门", 31.291526, 121.500333, "南区入口",
                quality="amap_poi", source="https://ditu.amap.com/place/B00155K7SZ",
            ),
            _location("本部食堂", 31.298650, 121.503900, "本部主食堂"),
            _location("南区食堂", 31.292300, 121.500800, "南区学生食堂"),
            _location(
                "文科图书馆", 31.296125, 121.505180, "文科主图书馆",
                quality="amap_poi", source="https://ditu.amap.com/place/B001559HJF",
            ),
            _location("理科图书馆", 31.299200, 121.503600, "理科图书馆"),
            _location(
                "光华楼", 31.300023, 121.505283, "标志性教学办公楼",
                quality="amap_poi", source="https://ditu.amap.com/place/B00155K7SX",
            ),
            _location("相辉堂", 31.298750, 121.502300, "历史建筑与演出场地"),
            _location("学生活动中心", 31.297300, 121.507500, "社团活动场地"),
            _location("南区学生公寓", 31.293000, 121.499300, "南区主要宿舍区"),
            _location("本部体育场", 31.301000, 121.508000, "本部运动场"),
            _location("燕园", 31.299000, 121.501000, "校园景观区"),
        ],
    },
    "zju": {
        "center_lat": 30.304850,
        "center_lng": 120.081700,
        "bounds": (30.2940, 30.3130, 120.0730, 120.0910),
        "center_quality": "demo_approximate",
        "center_source": "高德底图紫金港校区东西区覆盖范围中心",
        "locations": [
            _location(
                "紫金港校门", 30.295381, 120.082144, "紫金港南1门",
                quality="amap_poi", source="https://ditu.amap.com/place/B0FFKEYT1Y",
            ),
            _location("东区校门", 30.299500, 120.089500, "东区入口"),
            _location("西区食堂", 30.306500, 120.076500, "西区大食堂"),
            _location("东区食堂", 30.305500, 120.086000, "东区学生食堂"),
            _location("图书馆", 30.305200, 120.080300, "主图书馆"),
            _location("体育馆", 30.310100, 120.081800, "综合体育馆"),
            _location("田径场", 30.309200, 120.077800, "主田径场"),
            _location("教学楼群", 30.302800, 120.083000, "主要教学区"),
            _location("学生公寓", 30.306800, 120.087200, "学生宿舍区"),
            _location("启真湖", 30.301900, 120.080500, "校园水域景观"),
            _location("学生活动中心", 30.299800, 120.078800, "社团活动场地"),
            _location("快递服务中心", 30.307500, 120.084500, "校园快递点"),
        ],
    },
}


def location_tuples(school_code: str) -> list[tuple[str, float, float, str]]:
    """Return the tuple shape consumed by the existing seed pipeline."""
    return [
        (item["name"], item["latitude"], item["longitude"], item["description"])
        for item in DEMO_SCHOOL_COORDINATES[school_code]["locations"]
    ]
