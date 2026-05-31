"""
数据分析 API 路由
"""
import json
import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import pandas as pd

from analyzer import DataProcessor, DataVisualizer, MLModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局实例
processor = DataProcessor()
visualizer = DataVisualizer()
ml_model = None


class AnalysisRequest(BaseModel):
    """统计分析请求"""
    data: Optional[List[dict]] = None
    source_file: Optional[str] = None
    operations: List[str] = ["summary"]  # summary, describe, correlation


class VisualizationRequest(BaseModel):
    """可视化请求"""
    chart_type: str  # line, bar, pie, histogram, scatter, heatmap, box
    x: Optional[str] = None
    y: Optional[str] = None
    y_list: Optional[List[str]] = None
    title: str = ""
    source_file: Optional[str] = None


class TrainRequest(BaseModel):
    """模型训练请求"""
    feature_cols: List[str]
    target_col: str
    model_name: str = "auto"
    task_type: str = "classification"
    test_size: float = 0.2


@router.post("/upload")
async def upload_data(file: UploadFile = File(...)):
    """上传数据文件"""
    try:
        from config import RAW_DATA_DIR
        content = await file.read()
        file_path = RAW_DATA_DIR / file.filename
        file_path.write_bytes(content)

        if file.filename.endswith(".csv"):
            df = processor.load_csv(file_path)
        elif file.filename.endswith(".json"):
            df = processor.load_json(file_path)
        else:
            raise HTTPException(status_code=400, f"不支持的文件格式: {file.filename}")

        return {
            "success": True,
            "file": file.filename,
            "shape": list(df.shape),
            "columns": list(df.columns),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_data(req: AnalysisRequest):
    """数据分析入口"""
    try:
        # 加载数据
        if req.data:
            processor.from_dict(req.data)
        elif req.source_file:
            path = Path(req.source_file)
            if not path.exists():
                raise HTTPException(status_code=404, "文件不存在")
            if path.suffix == ".csv":
                processor.load_csv(path)
            else:
                processor.load_json(path)
        else:
            raise HTTPException(status_code=400, "请提供数据或文件路径")

        # 自动清洗
        processor.clean()

        results = {}
        if "summary" in req.operations:
            results["summary"] = processor.summary()
        if "describe" in req.operations:
            desc = processor.describe()
            results["describe"] = desc.fillna("").to_dict()
        if "correlation" in req.operations:
            corr = processor.correlation()
            results["correlation"] = corr.fillna("").to_dict()

        return {"success": True, "source": processor.source_name, "results": results}

    except Exception as e:
        logger.exception("分析异常")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/visualize")
async def create_chart(req: VisualizationRequest):
    """创建图表"""
    try:
        # 加载数据
        if req.source_file:
            path = Path(req.source_file)
            if not path.exists():
                raise HTTPException(status_code=404, "文件不存在")
            df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_json(path)
        else:
            raise HTTPException(status_code=400, "请提供数据")

        chart_funcs = {
            "line": lambda: visualizer.line_chart(df, req.x, req.y, req.title),
            "bar": lambda: visualizer.bar_chart(df, req.x, req.y, req.title),
            "pie": lambda: visualizer.pie_chart(df[req.x].value_counts(), req.title),
            "histogram": lambda: visualizer.histogram(df[req.x], title=req.title),
            "scatter": lambda: visualizer.scatter(df, req.x, req.y, title=req.title),
            "heatmap": lambda: visualizer.correlation_heatmap(df, req.title),
            "box": lambda: visualizer.box_plot(df, title=req.title),
        }

        if req.chart_type not in chart_funcs:
            raise HTTPException(status_code=400, f"不支持的图表类型: {req.chart_type}")

        chart_base64 = chart_funcs[req.chart_type]()
        return {"success": True, "chart": chart_base64}

    except Exception as e:
        logger.exception("图表生成异常")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def train_model(req: TrainRequest):
    """训练机器学习模型"""
    global ml_model
    try:
        from config import RAW_DATA_DIR
        # 找最近的数据文件
        csv_files = list(RAW_DATA_DIR.glob("*.csv"))
        if not csv_files:
            raise HTTPException(status_code=400, "请先上传训练数据")

        latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
        df = pd.read_csv(latest_file)

        ml_model = MLModel(task_type=req.task_type)
        X, y = ml_model.load_data(df, req.feature_cols, req.target_col)
        if y is None:
            raise HTTPException(status_code=400, "缺少目标列")

        X_train, X_test, y_train, y_test = ml_model.train_test_split(X, y)
        ml_model.choose_model(req.model_name)
        ml_model.train(X_train, y_train)
        metrics = ml_model.evaluate(X_test, y_test)
        importance = ml_model.get_feature_importance()

        return {
            "success": True,
            "model": ml_model.model_name,
            "metrics": metrics,
            "feature_importance": importance,
            "data_shape": list(X.shape),
        }

    except Exception as e:
        logger.exception("训练异常")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict(data: List[dict]):
    """使用已训练的模型进行预测"""
    global ml_model
    if ml_model is None or not ml_model._is_fitted:
        raise HTTPException(status_code=400, "请先训练模型")

    try:
        df = pd.DataFrame(data)
        X = df[ml_model.features]
        predictions = ml_model.predict(X)
        return {
            "success": True,
            "predictions": predictions.tolist(),
            "features": ml_model.features,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
