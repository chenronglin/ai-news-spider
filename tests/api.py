import asyncio
from crawl4ai import Crawl4aiDockerClient

# 主异步函数
async def main():
    async with Crawl4aiDockerClient(base_url="http://118.195.150.71:11235") as client:
        # 重点：删除所有 hooks 相关代码！
        result = await client.crawl(
            ["https://cmm.ncut.edu.cn/index/tzgg.htm"],
        )

        print(f"Success: {result.success}")
        print(f"HTML 长度: {len(result.html)} 字符")
        
        # 把 HTML 打印出来，你就能用之前的解析代码提取新闻了
        print("\n===== 页面 HTML 内容 =====\n")
        print(result.html)

# 运行
if __name__ == "__main__":
    asyncio.run(main())