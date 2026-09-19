# TWStockDataPipeline

可公開的台股資料下載、正規化、驗證與發布 staging tree。此目錄刻意不包含 Fair Value、Quant、AI、Backtest、私有 prompt 或任何 secret。

## 執行

```bash
python scripts/catchup.py --data-root data --state state/pipeline_state.json --health data/data_health.json
python scripts/generate_health.py --data-root data --state state/pipeline_state.json --output data/data_health.json
```

資料來源只使用官方公開端點；寫入採 atomic replace，checkpoint 可提交至 distribution repository 或由 object storage/CI artifact 保存。

搬移到 `alien0077/TWStockDataPipeline` 後，GitHub Actions 使用 `ubuntu-latest`，不需要 Oracle runner。
