from datetime import date
from src.common.spark_session import get_spark
from src.model.runtime.unifying_model import UnifyingModel
from src.model.loaders.parquet_loader import ParquetLoader

spark = get_spark("Company_UnifyingModel")
params = {"DATE_FROM": "2024-01-01", "DATE_TO": "2024-01-05", "SNAPSHOT_DT": ""}
model = UnifyingModel(spark, "configs/model_company.yaml", "configs/storage.json", params=params)
dims, facts = model.build()
loader = ParquetLoader(root="storage")
snap = date.today().strftime("%Y-%m-%d")
for name, df in dims.items():  loader.write_dim(name, df, snapshot_dt=snap)
for name, df in facts.items(): loader.write_fact(name, df, snapshot_dt=snap)
print("✅ silver written from config")
