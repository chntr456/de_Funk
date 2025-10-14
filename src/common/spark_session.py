from pyspark.sql import SparkSession

def get_spark(app_name: str = "FacetDocumentPolygon"):
    return SparkSession.builder.appName(app_name).getOrCreate()
