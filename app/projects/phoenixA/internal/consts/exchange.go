package consts

// Exchange codes — globally stable identifiers for trading venues (uppercase).
// Part of the security_registry natural key (exchange, asset_type, symbol);
// phoenixA normalizes exchange to upper case on write (refactor §3.1/§6 R1).
//
// These are the code-side source of truth; they mirror the
// govern.data_enum_dictionary rows where source='phoenixa' and
// enum_name='exchange' (refactor §3.3: const value == enum code). When the
// platform extends to new venues, add a const here AND a matching enum row in
// migrations/postgresql/security/0005_govern_phoenixa_meta_enums.sql.
//
// exchange (trading venue) is distinct from market (business partition):
// zh_a ↔ SH/SZ/BJ is one-to-many (refactor §3.4/§8 Q5).
const (
	EXCHANGE_SH = "SH" // 上海证券交易所
	EXCHANGE_SZ = "SZ" // 深圳证券交易所
	EXCHANGE_BJ = "BJ" // 北京证券交易所
)
