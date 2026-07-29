"""MAP-GCJ-01: align three-school demo coordinates with AMap GCJ-02.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-29 21:00:00.000000

Only rows that still contain the repository's previous demo coordinates are
updated. This protects locations that an operator has already corrected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHOOL_COORDINATES = [
    ("jiangnan", 31.483706, 120.271166, 31.483652, 120.271160),
    ("fudan", 31.298300, 121.502000, 31.297920, 121.503540),
    ("zju", 30.309700, 120.121600, 30.304850, 120.081700),
]

LOCATION_COORDINATES = [
    ("jiangnan", "北门", 31.4863, 120.2712, 31.490227, 120.269806),
    ("jiangnan", "南门", 31.4812, 120.2712, 31.474719, 120.272855),
    ("jiangnan", "第一食堂", 31.4840, 120.2700, 31.484820, 120.266820),
    ("jiangnan", "第二食堂", 31.4845, 120.2725, 31.479920, 120.275560),
    ("jiangnan", "图书馆", 31.4835, 120.2715, 31.480930, 120.270080),
    ("jiangnan", "体育馆", 31.4855, 120.2735, 31.486660, 120.276420),
    ("jiangnan", "田径场", 31.4850, 120.2745, 31.487180, 120.277560),
    ("jiangnan", "教学楼A区", 31.4842, 120.2710, 31.484180, 120.272180),
    ("jiangnan", "学士公寓", 31.4825, 120.2730, 31.477760, 120.276520),
    ("jiangnan", "校园超市", 31.4838, 120.2720, 31.478620, 120.275180),
    ("jiangnan", "文浩科学馆", 31.4830, 120.2705, 31.481880, 120.266420),
    ("jiangnan", "大学生活动中心", 31.4828, 120.2728, 31.478880, 120.268420),
    ("jiangnan", "蠡湖畔", 31.4820, 120.2718, 31.482020, 120.271820),
    ("jiangnan", "快递服务中心", 31.4833, 120.2738, 31.476820, 120.267880),
    ("jiangnan", "打印文印店", 31.4847, 120.2708, 31.483860, 120.273520),
    ("fudan", "邯郸路校门", 31.2989, 121.5015, 31.300512, 121.507121),
    ("fudan", "南区校门", 31.2955, 121.5020, 31.291526, 121.500333),
    ("fudan", "本部食堂", 31.2985, 121.5025, 31.298650, 121.503900),
    ("fudan", "南区食堂", 31.2960, 121.5028, 31.292300, 121.500800),
    ("fudan", "文科图书馆", 31.2978, 121.5018, 31.296125, 121.505180),
    ("fudan", "理科图书馆", 31.2992, 121.5022, 31.299200, 121.503600),
    ("fudan", "光华楼", 31.2975, 121.5010, 31.300023, 121.505283),
    ("fudan", "相辉堂", 31.2982, 121.5008, 31.298750, 121.502300),
    ("fudan", "学生活动中心", 31.2970, 121.5030, 31.297300, 121.507500),
    ("fudan", "南区学生公寓", 31.2958, 121.5035, 31.293000, 121.499300),
    ("fudan", "本部体育场", 31.2995, 121.5030, 31.301000, 121.508000),
    ("fudan", "燕园", 31.2972, 121.5015, 31.299000, 121.501000),
    ("zju", "紫金港校门", 30.3105, 120.1210, 30.295381, 120.082144),
    ("zju", "东区校门", 30.3085, 120.1245, 30.299500, 120.089500),
    ("zju", "西区食堂", 30.3095, 120.1200, 30.306500, 120.076500),
    ("zju", "东区食堂", 30.3090, 120.1235, 30.305500, 120.086000),
    ("zju", "图书馆", 30.3100, 120.1220, 30.305200, 120.080300),
    ("zju", "体育馆", 30.3110, 120.1225, 30.310100, 120.081800),
    ("zju", "田径场", 30.3108, 120.1218, 30.309200, 120.077800),
    ("zju", "教学楼群", 30.3092, 120.1212, 30.302800, 120.083000),
    ("zju", "学生公寓", 30.3080, 120.1230, 30.306800, 120.087200),
    ("zju", "启真湖", 30.3102, 120.1215, 30.301900, 120.080500),
    ("zju", "学生活动中心", 30.3098, 120.1228, 30.299800, 120.078800),
    ("zju", "快递服务中心", 30.3088, 120.1222, 30.307500, 120.084500),
]


def _update_schools(reverse: bool = False) -> None:
    connection = op.get_bind()
    statement = sa.text(
        """
        UPDATE schools
           SET center_lat = :new_lat,
               center_lng = :new_lng,
               updated_at = CURRENT_TIMESTAMP
         WHERE code = :school_code
           AND ABS(center_lat - :old_lat) < 0.0000001
           AND ABS(center_lng - :old_lng) < 0.0000001
        """
    )
    for code, old_lat, old_lng, new_lat, new_lng in SCHOOL_COORDINATES:
        if reverse:
            old_lat, new_lat = new_lat, old_lat
            old_lng, new_lng = new_lng, old_lng
        connection.execute(statement, {
            "school_code": code,
            "old_lat": old_lat,
            "old_lng": old_lng,
            "new_lat": new_lat,
            "new_lng": new_lng,
        })


def _update_locations(reverse: bool = False) -> None:
    connection = op.get_bind()
    statement = sa.text(
        """
        UPDATE locations AS location
           SET latitude = :new_lat,
               longitude = :new_lng,
               updated_at = CURRENT_TIMESTAMP
          FROM schools AS school
         WHERE location.school_id = school.id
           AND school.code = :school_code
           AND location.name = :location_name
           AND location.latitude = CAST(:old_lat AS NUMERIC(10, 7))
           AND location.longitude = CAST(:old_lng AS NUMERIC(10, 7))
        """
    )
    for code, name, old_lat, old_lng, new_lat, new_lng in LOCATION_COORDINATES:
        if reverse:
            old_lat, new_lat = new_lat, old_lat
            old_lng, new_lng = new_lng, old_lng
        connection.execute(statement, {
            "school_code": code,
            "location_name": name,
            "old_lat": old_lat,
            "old_lng": old_lng,
            "new_lat": new_lat,
            "new_lng": new_lng,
        })


def upgrade() -> None:
    _update_schools()
    _update_locations()


def downgrade() -> None:
    _update_locations(reverse=True)
    _update_schools(reverse=True)
