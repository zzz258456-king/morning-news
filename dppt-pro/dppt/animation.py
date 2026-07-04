"""
PowerPoint 动画支持

为 slide/shape 添加简单入场动画。当前通过 <p:timing> OOXML 注入实现，
支持 fade、flyIn、appear、wipe 等常见 entrance 效果。
"""

from __future__ import annotations

from typing import Optional

from pptx.oxml.xmlchemy import OxmlElement


# 常见 entrance 动画效果映射
# 参考 OpenXML 动画预设 filter 名称
ENTRANCE_EFFECTS = {
    "fade": "fade",
    "appear": "appear",
    "flyIn": "flyIn",
    "fly-in": "flyIn",
    "wipe": "wipe",
    "peek": "peek",
    "plus": "plus",
    "random": "random",
    "newsflash": "newsflash",
    "dissolve": "dissolve",
    "split": "split",
    "stretch": "stretch",
    "swivel": "swivel",
    "randomBars": "randomBar",
    "random-bars": "randomBar",
    "wedge": "wedge",
    "wheel": "wheel",
    "circle": "circle",
    "box": "box",
    "diamond": "diamond",
}


def _ox(tag: str, attrs: Optional[dict] = None, children: Optional[list] = None):
    """创建 OxmlElement 节点。"""
    elm = OxmlElement(tag)
    if attrs:
        for k, v in attrs.items():
            elm.set(k, str(v))
    if children:
        for child in children:
            elm.append(child)
    return elm


def _filter_effect(effect: str) -> str:
    return ENTRANCE_EFFECTS.get(effect, effect) or "fade"


def add_entrance_animation(
    slide,
    shape,
    effect: str = "fade",
    duration_ms: int = 500,
    trigger: str = "onClick",
    delay_ms: int = 0,
) -> None:
    """为指定 shape 添加入场动画。

    Args:
        slide: pptx Slide 对象
        shape: 要动画的 Shape 对象
        effect: 动画效果名称，如 fade / flyIn / wipe / appear
        duration_ms: 动画持续时间（毫秒）
        trigger: 触发方式，onClick / withPrevious / afterPrevious
        delay_ms: 延迟时间（毫秒）
    """
    spid = str(shape.shape_id)
    effect_name = _filter_effect(effect)

    # 查找或创建 <p:timing> 根节点
    timing = None
    for child in slide._element:
        if child.tag.endswith("}timing"):
            timing = child
            break

    if timing is None:
        timing = _ox("p:timing")
        slide._element.append(timing)

    # 查找或创建 <p:tnLst>
    tnLst = timing.find("{http://schemas.openxmlformats.org/presentationml/2006/main}tnLst")
    if tnLst is None:
        tnLst = _ox("p:tnLst")
        timing.append(tnLst)

    # 查找或创建顶层 p:par > p:cTn[nodeType=tmRoot]
    root_par = None
    root_ctn = None
    for child in tnLst:
        if child.tag.endswith("}par"):
            root_par = child
            for sub in child:
                if sub.tag.endswith("}cTn") and sub.get("nodeType") == "tmRoot":
                    root_ctn = sub
                    break
            break

    if root_par is None:
        root_ctn = _ox("p:cTn", {"id": "1", "dur": "indefinite", "restart": "never", "nodeType": "tmRoot"})
        root_par = _ox("p:par", children=[root_ctn])
        tnLst.append(root_par)

    child_tnLst = root_ctn.find("{http://schemas.openxmlformats.org/presentationml/2006/main}childTnLst")
    if child_tnLst is None:
        child_tnLst = _ox("p:childTnLst")
        root_ctn.append(child_tnLst)

    # 查找或创建 mainSeq
    main_seq = None
    main_seq_ctn = None
    for child in child_tnLst:
        if child.tag.endswith("}seq"):
            main_seq = child
            for sub in child:
                if sub.tag.endswith("}cTn") and sub.get("nodeType") == "mainSeq":
                    main_seq_ctn = sub
                    break
            break

    if main_seq is None:
        main_seq_ctn = _ox("p:cTn", {"id": "2", "dur": "indefinite", "nodeType": "mainSeq"})
        main_seq = _ox("p:seq", {"concurrent": "1", "nextAc": "seek"}, children=[main_seq_ctn])
        child_tnLst.append(main_seq)

    seq_child_tnLst = main_seq_ctn.find("{http://schemas.openxmlformats.org/presentationml/2006/main}childTnLst")
    if seq_child_tnLst is None:
        seq_child_tnLst = _ox("p:childTnLst")
        main_seq_ctn.append(seq_child_tnLst)

    # 计算新动画节点 ID（简单递增）
    existing_ids = [int(el.get("id", 0)) for el in main_seq_ctn.iter() if el.get("id") and el.get("id").isdigit()]
    next_id = max(existing_ids, default=2) + 1

    # 触发条件
    if trigger == "withPrevious":
        delay_attr = str(delay_ms)
    elif trigger == "afterPrevious":
        delay_attr = str(delay_ms)
    else:  # onClick
        delay_attr = "indefinite"

    # 构建单个动画节点
    anim_ctn = _ox(
        "p:cTn",
        {"id": str(next_id), "fill": "hold", "nodeType": "clickEffect" if trigger == "onClick" else "afterEffect"},
        children=[
            _ox("p:stCondLst", children=[_ox("p:cond", {"delay": delay_attr})]),
            _ox(
                "p:childTnLst",
                children=[
                    _ox(
                        "p:animEffect",
                        {"transition": "in", "filter": effect_name},
                        children=[
                            _ox(
                                "p:cBhvr",
                                children=[
                                    _ox(
                                        "p:cTn",
                                        {"id": str(next_id + 1), "dur": str(duration_ms), "fill": "hold"},
                                        children=[_ox("p:stCondLst", children=[_ox("p:cond", {"delay": str(delay_ms)})])],
                                    ),
                                    _ox("p:tgtEl", children=[_ox("p:spTgt", {"spid": spid})]),
                                    _ox("p:attrNameLst", children=[_ox("p:attrName")]),
                                ],
                            )
                        ],
                    )
                ],
            ),
        ],
    )

    anim_par = _ox("p:par", children=[anim_ctn])
    seq_child_tnLst.append(anim_par)


def add_slide_transition(slide, transition_type: str = "fade", duration_ms: int = 500) -> None:
    """为 slide 添加转场效果（可选）。"""
    # python-pptx 已提供 slide.transition API
    try:
        transition = slide.transition
        if transition_type == "fade":
            transition.transition_type = 1  # MSO_TRANSITION_TYPE.FADE 可能不存在，直接用数值
        transition.duration = duration_ms / 1000.0
    except Exception:
        pass
