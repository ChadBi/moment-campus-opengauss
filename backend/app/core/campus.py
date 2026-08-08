"""校园身份认证与注册学校相关的纯权限辅助函数。"""


def get_registration_school_id(user) -> int:
    """返回用户注册时选择的学校。

    registration_school_id 在新数据中是明确字段；历史数据迁移前可能为空，
    回退到 school_id 以兼容旧用户和直接构造的测试用户。
    """
    registration_school_id = getattr(user, "registration_school_id", None)
    return int(registration_school_id or user.school_id)


def is_registration_school(user, school_id: int | None) -> bool:
    """判断请求租户是否为用户注册时选择的学校。"""
    if school_id is None:
        return False
    return get_registration_school_id(user) == int(school_id)
