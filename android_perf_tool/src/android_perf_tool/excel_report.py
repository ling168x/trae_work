import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
import os

class ExcelReport:
    @staticmethod
    def generate(data: List[Dict[str, Any]], summary: Dict[str, Any], output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        df = pd.DataFrame(data)
        
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="原始数据", index=False)
            
            summary_df = pd.DataFrame({
                "指标": [
                    "总采样数",
                    "测试时长(秒)",
                    "FPS最小值",
                    "FPS最大值",
                    "FPS平均值",
                    "卡顿帧数",
                    "卡顿率(%)",
                    "CPU最小值(%)",
                    "CPU最大值(%)",
                    "CPU平均值(%)",
                    "内存最小值(MB)",
                    "内存最大值(MB)",
                    "内存平均值(MB)"
                ],
                "数值": [
                    summary.get("total_samples", 0),
                    summary.get("duration", 0),
                    summary.get("fps", {}).get("min", 0),
                    summary.get("fps", {}).get("max", 0),
                    summary.get("fps", {}).get("avg", 0),
                    summary.get("fps", {}).get("janky_count", 0),
                    summary.get("fps", {}).get("janky_rate", 0),
                    summary.get("cpu", {}).get("min", 0),
                    summary.get("cpu", {}).get("max", 0),
                    summary.get("cpu", {}).get("avg", 0),
                    summary.get("memory", {}).get("min", 0),
                    summary.get("memory", {}).get("max", 0),
                    summary.get("memory", {}).get("avg", 0)
                ]
            })
            summary_df.to_excel(writer, sheet_name="汇总报告", index=False)
        
        return output_path