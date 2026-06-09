import pandas as pd

# 1. Load the immutable parquet file into memory
df = pd.read_parquet('gourmet_cache.parquet')

# 2. Apply your edits
df = df[~df['name'].str.contains('食べログ', na=False)]

# 3. Save the modifications by overwriting the old file
df.to_parquet('gourmet_cache.parquet', index=False)
