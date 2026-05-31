"""
机器学习模型模块
提供分类、回归、聚类、特征工程等常用ML功能
"""
import json
import logging
from pathlib import Path
from typing import Optional, Union, Any, Dict
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_squared_error, mean_absolute_error, r2_score,
    confusion_matrix, classification_report
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.cluster import KMeans
from sklearn.svm import SVC

from config import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


class MLModel:
    """
    机器学习模型管理器
    支持分类、回归、聚类，以及模型评估与保存
    """

    MODEL_REGISTRY = {
        "classification": {
            "logistic": LogisticRegression(max_iter=1000),
            "random_forest": RandomForestClassifier(n_estimators=100, random_state=42),
            "svm": SVC(probability=True, random_state=42),
        },
        "regression": {
            "linear": LinearRegression(),
            "random_forest": RandomForestRegressor(n_estimators=100, random_state=42),
        },
        "clustering": {
            "kmeans": KMeans(n_clusters=3, random_state=42, n_init=10),
        },
    }

    def __init__(self, task_type: str = "classification"):
        if task_type not in self.MODEL_REGISTRY:
            raise ValueError(f"不支持的任务类型: {task_type}，可选: {list(self.MODEL_REGISTRY.keys())}")
        self.task_type = task_type
        self.model = None
        self.model_name = ""
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.features: list = []
        self.target: str = ""
        self._is_fitted = False
        self.metrics: Dict = {}

    def load_data(self, data: pd.DataFrame, feature_cols: list,
                  target_col: str = None) -> tuple:
        """
        准备训练数据
        返回 (X, y) 或 (X, None)
        """
        self.features = feature_cols
        self.target = target_col or ""

        X = data[feature_cols].copy()

        # 处理特征中的非数值列
        for col in X.columns:
            if X[col].dtype == object:
                X[col] = self.label_encoder.fit_transform(X[col].astype(str))

        # 填充缺失值
        X = X.fillna(X.median())

        y = None
        if target_col and target_col in data.columns:
            y = data[target_col]
            if y.dtype == object:
                y = self.label_encoder.fit_transform(y.astype(str))
            y = y.fillna(y.mode()[0] if not y.mode().empty else 0)

        return X, y

    def choose_model(self, model_name: str = "auto"):
        """
        自动或手动选择模型
        """
        if model_name == "auto":
            if self.task_type == "classification":
                model_name = "random_forest"  # 默认用随机森林
            elif self.task_type == "regression":
                model_name = "random_forest"
            else:
                model_name = "kmeans"

        available = self.MODEL_REGISTRY.get(self.task_type, {})
        if model_name not in available:
            raise ValueError(f"模型 '{model_name}' 不在 {self.task_type} 的可用列表中: {list(available.keys())}")

        self.model = available[model_name]
        self.model_name = model_name
        logger.info(f"已选择模型: {model_name} ({self.task_type})")
        return self.model

    def train(self, X, y=None) -> Any:
        """
        训练模型
        分类/回归: 需要 X, y
        聚类: 只需要 X
        """
        if self.model is None:
            self.choose_model()

        # 特征标准化
        if self.task_type != "clustering":
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = X.values if hasattr(X, 'values') else X

        if self.task_type == "clustering":
            self.model.fit(X_scaled)
            if hasattr(self.model, 'labels_'):
                self.metrics["labels"] = self.model.labels_.tolist()
                self.metrics["inertia"] = float(self.model.inertia_)
        else:
            self.model.fit(X_scaled, y)

        self._is_fitted = True
        logger.info(f"模型训练完成: {self.model_name}")
        return self.model

    def predict(self, X) -> np.ndarray:
        """使用训练好的模型进行预测"""
        if not self._is_fitted:
            raise ValueError("模型尚未训练，请先调用 train()")

        X_scaled = self.scaler.transform(X) if self.task_type != "clustering" else X
        return self.model.predict(X_scaled)

    def evaluate(self, X_test, y_test) -> dict:
        """
        评估模型性能
        返回评估指标字典
        """
        if self.task_type == "clustering":
            logger.warning("聚类模型暂不支持监督评估指标")
            return self.metrics

        y_pred = self.predict(X_test)

        if self.task_type == "classification":
            self.metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
                "f1_score": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
                "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            }
        elif self.task_type == "regression":
            self.metrics = {
                "mse": float(mean_squared_error(y_test, y_pred)),
                "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
                "mae": float(mean_absolute_error(y_test, y_pred)),
                "r2_score": float(r2_score(y_test, y_pred)),
            }

        logger.info(f"模型评估完成: {self.metrics}")
        return self.metrics

    def train_test_split(self, X, y, test_size: float = 0.2,
                         random_state: int = 42) -> tuple:
        """划分训练集和测试集"""
        return train_test_split(X, y, test_size=test_size, random_state=random_state)

    def cross_validate(self, X, y, cv: int = 5) -> dict:
        """交叉验证"""
        if self.model is None or not self._is_fitted:
            raise ValueError("请先训练模型")

        scoring = "accuracy" if self.task_type == "classification" else "r2"
        scores = cross_val_score(self.model, X, y, cv=cv, scoring=scoring)
        result = {
            "scores": scores.tolist(),
            "mean": float(scores.mean()),
            "std": float(scores.std()),
        }
        logger.info(f"交叉验证: {result}")
        return result

    def grid_search(self, X, y, param_grid: dict, cv: int = 3) -> dict:
        """网格搜索调参"""
        if self.model is None:
            self.choose_model()

        grid = GridSearchCV(
            self.model, param_grid, cv=cv,
            scoring="accuracy" if self.task_type == "classification" else "r2",
            n_jobs=-1, verbose=0
        )
        grid.fit(X, y)
        self.model = grid.best_estimator_
        self._is_fitted = True
        result = {
            "best_params": grid.best_params_,
            "best_score": float(grid.best_score_),
        }
        logger.info(f"网格搜索完成: {result}")
        return result

    def save_model(self, name: str = None) -> str:
        """导出模型信息（为简化，导出配置而非pickle）"""
        if name is None:
            name = f"{self.model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output = {
            "model_name": self.model_name,
            "task_type": self.task_type,
            "features": self.features,
            "target": self.target,
            "metrics": self.metrics,
            "is_fitted": self._is_fitted,
        }
        output_path = PROCESSED_DATA_DIR / f"{name}.json"
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"模型信息已保存: {output_path}")
        return str(output_path)

    def get_feature_importance(self) -> Optional[dict]:
        """获取特征重要性（树模型）"""
        if hasattr(self.model, "feature_importances_"):
            importance = self.model.feature_importances_
            return dict(zip(self.features, importance.tolist()))
        logger.warning(f"模型 {self.model_name} 不支持特征重要性分析")
        return None
