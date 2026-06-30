package controller

import (
	"encoding/json"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestLongHuBangJSONDeserialization(t *testing.T) {
	artemisPayload := `[{"source":"amazing_data","symbol":"000001","market":"zh_a","trade_date":"2026-05-27","security_name":"平安银行","reason_type":"1001","reason_type_name":"日涨幅偏离值达7%","trader_name":"国泰君安证券上海分公司","flow_mark":1,"change_range":9.98,"buy_amount":123456789.12,"sell_amount":98765432.10,"total_amount":24680246.80,"total_volume":321.50}]`

	var list []*model.LongHuBang
	if err := json.Unmarshal([]byte(artemisPayload), &list); err != nil {
		t.Fatalf("failed to unmarshal Artemis long_hu_bang payload: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 record, got %d", len(list))
	}

	rec := list[0]
	assertEqual(t, "source", rec.Source, "amazing_data")
	assertEqual(t, "symbol", rec.Symbol, "000001")
	assertEqual(t, "market", rec.Market, "zh_a")
	assertEqual(t, "trade_date", rec.TradeDate, "2026-05-27")
	assertEqual(t, "reason_type", rec.ReasonType, "1001")
	assertEqual(t, "trader_name", rec.TraderName, "国泰君安证券上海分公司")
	assertEqual(t, "security_name", rec.SecurityName, "平安银行")
	assertEqual(t, "reason_type_name", rec.ReasonTypeName, "日涨幅偏离值达7%")
	if rec.FlowMark != 1 {
		t.Fatalf("expected flow_mark=1, got %d", rec.FlowMark)
	}
	if rec.ChangeRange != 9.98 {
		t.Errorf("expected change_range=9.98, got %v", rec.ChangeRange)
	}
	if rec.BuyAmount != 123456789.12 {
		t.Errorf("expected buy_amount=123456789.12, got %v", rec.BuyAmount)
	}
}

func TestLongHuBangDefaultMarketAndDateNormalization(t *testing.T) {
	payload := `[{"symbol":"000001","trade_date":"20260527","security_name":"平安银行","reason_type":"1001","reason_type_name":"日涨幅偏离值达7%","trader_name":"国泰君安证券上海分公司","flow_mark":2,"change_range":-5.2,"buy_amount":100.0,"sell_amount":200.0,"total_amount":300.0,"total_volume":10.0}]`

	var list []*model.LongHuBang
	if err := json.Unmarshal([]byte(payload), &list); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	for _, item := range list {
		item.Source = "amazing_data"
		if item.Market == "" {
			item.Market = "zh_a"
		}
		item.TradeDate = normalizeDateYYYYMMDD(item.TradeDate)
	}

	assertEqual(t, "source", list[0].Source, "amazing_data")
	assertEqual(t, "market", list[0].Market, "zh_a")
	assertEqual(t, "trade_date", list[0].TradeDate, "2026-05-27")
	if list[0].FlowMark != 2 {
		t.Fatalf("expected flow_mark=2, got %d", list[0].FlowMark)
	}
	if list[0].TotalAmount != 300.0 {
		t.Fatalf("expected total_amount=300.0, got %v", list[0].TotalAmount)
	}
}
