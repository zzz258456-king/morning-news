import sys
import uvicorn

if __name__ == "__main__":
    # 生产模式：无热重载，直接运行
    # 开发模式：带热重载
    is_dev = len(sys.argv) > 1 and sys.argv[1] == "dev"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=is_dev,
        workers=1,
    )
