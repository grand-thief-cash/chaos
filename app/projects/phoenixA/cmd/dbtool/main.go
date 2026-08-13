package main

// Temporary one-off DB tool for atlas_kg sample/governance inspection & cleanup.
// Reuses phoenixA's existing gorm/postgres deps (no new dependencies).
// Usage: PHOENIXA_DB_DSN='...' go run ./cmd/dbtool inspect
// Destructive operations additionally require --confirm-delete.

import (
	"encoding/json"
	"fmt"
	"os"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func main() {
	dsn := os.Getenv("PHOENIXA_DB_DSN")
	if dsn == "" {
		die("PHOENIXA_DB_DSN is required")
	}
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		die("connect: %v", err)
	}
	cmd := "inspect"
	if len(os.Args) > 1 {
		cmd = os.Args[1]
	}
	switch cmd {
	case "inspect":
		inspect(db)
	case "errors":
		errors(db)
	case "reports":
		reports(db)
	case "review":
		review(db)
	case "delete":
		requireDeleteConfirmation()
		del(db, false)
	case "delete-all":
		requireDeleteConfirmation()
		del(db, true)
	default:
		fmt.Println("usage: dbtool [inspect|reports|review|errors|delete|delete-all] [--confirm-delete]")
		os.Exit(2)
	}
}

func requireDeleteConfirmation() {
	if len(os.Args) < 3 || os.Args[2] != "--confirm-delete" {
		die("destructive command requires --confirm-delete")
	}
}

func errors(db *gorm.DB) {
	type er struct{ Id, Status, Code, Msg string }
	var ers []er
	db.Raw("select id, status, coalesce(error_code,''), coalesce(error_message,'') from atlas_kg.sample_run order by created_at desc limit 10").Scan(&ers)
	for _, e := range ers {
		fmt.Printf("  %s status=%s code=%s\n    msg: %s\n", e.Id, e.Status, e.Code, e.Msg)
	}
	fmt.Println("\n-- failed extraction_runs --")
	type ex struct{ Id, Status, Code, Msg, Doc string }
	var exs []ex
	db.Raw("select id, status, coalesce(error_code,''), coalesce(error_summary,''), source_document_id from atlas_kg.extraction_run where status like 'FAILED%' order by updated_at desc limit 10").Scan(&exs)
	for _, e := range exs {
		fmt.Printf("  %s doc=%s status=%s code=%s\n    msg: %s\n", e.Id, e.Doc, e.Status, e.Code, e.Msg)
	}
}

func reports(db *gorm.DB) {
	var total, dl int
	if err := db.Raw("select count(*) from ods.research_report_download_record").Row().Scan(&total); err != nil {
		fmt.Printf("count all error: %v\n", err)
		return
	}
	fmt.Printf("-- research_report_download_record total=%d --\n", total)
	if err := db.Raw("select count(*) from ods.research_report_download_record where status='downloaded'").Row().Scan(&dl); err != nil {
		fmt.Printf("count downloaded error: %v\n", err)
		return
	}
	fmt.Printf("-- status=downloaded: %d --\n", dl)
	fmt.Println("-- by report_type (downloaded) --")
	type rt struct {
		Type string
		N    int
	}
	var rts []rt
	res := db.Raw("select report_type as type, count(*) as n from ods.research_report_download_record where status='downloaded' group by report_type order by n desc").Scan(&rts)
	if res.Error != nil {
		fmt.Printf("by-type error: %v\n", res.Error)
	}
	for _, r := range rts {
		fmt.Printf("  %-20s %d\n", r.Type, r.N)
	}
	fmt.Println("\n-- latest downloaded (8 overall) --")
	type rr struct{ Type, Rid, Title, Date string }
	var rows []rr
	db.Raw("select report_type as type, resource_id as rid, coalesce(title,'') as title, publish_date as date from ods.research_report_download_record where status='downloaded' order by publish_date desc limit 8").Scan(&rows)
	for _, r := range rows {
		fmt.Printf("  [%s] %s %s %s\n", r.Type, r.Date, r.Rid, r.Title)
	}
}

func review(db *gorm.DB) {
	var id, status string
	var payload []byte
	err := db.Raw("select id, status, payload from atlas_kg.governance_record where kind='discovery' order by created_at desc limit 1").Row().Scan(&id, &status, &payload)
	if err != nil {
		fmt.Printf("review error: %v\n", err)
		return
	}
	fmt.Printf("== governance discovery %s status=%s ==\n", id, status)
	var p struct {
		RequestedSampleSize   int `json:"requested_sample_size"`
		ReportTypeAssessments []struct {
			ReportType string `json:"report_type"`
			Sampled    int    `json:"sampled_document_count"`
			Useful     int    `json:"useful_document_count"`
			Enabled    bool   `json:"enabled_for_production"`
			Profile    string `json:"prompt_profile_key"`
			Rationale  string `json:"rationale"`
		} `json:"report_type_assessments"`
		PredicateProposals []struct {
			Name    string   `json:"canonical_name"`
			Subject []string `json:"subject_types"`
			Object  []string `json:"object_types"`
			Count   int      `json:"occurrence_count"`
			Desc    string   `json:"description"`
			Status  string   `json:"status"`
		} `json:"predicate_proposals"`
		ConceptProposals []struct {
			Type  string `json:"concept_type"`
			Name  string `json:"canonical_name"`
			Count int    `json:"occurrence_count"`
		} `json:"concept_proposals"`
	}
	if err := json.Unmarshal(payload, &p); err != nil {
		fmt.Printf("unmarshal error: %v\n", err)
		return
	}
	fmt.Printf("requested_sample_size=%d\n", p.RequestedSampleSize)
	fmt.Println("\n-- report_type_assessments --")
	for _, r := range p.ReportTypeAssessments {
		fmt.Printf("  %-14s sampled=%d useful=%d enabled=%v profile=%s\n     %s\n", r.ReportType, r.Sampled, r.Useful, r.Enabled, r.Profile, r.Rationale)
	}
	fmt.Printf("\n-- predicate_proposals (%d) --\n", len(p.PredicateProposals))
	for _, pr := range p.PredicateProposals {
		fmt.Printf("  %-28s %s -> %s  count=%d [%s]\n     %s\n", pr.Name, join(pr.Subject), join(pr.Object), pr.Count, pr.Status, pr.Desc)
	}
	fmt.Printf("\n-- concept_proposals (%d) --\n", len(p.ConceptProposals))
	for _, c := range p.ConceptProposals {
		fmt.Printf("  %-14s %-30s count=%d\n", c.Type, c.Name, c.Count)
	}
	// raw_results doc count for this sample_run_id (governance id == sample_run_id)
	var docCount, catCount int
	db.Raw("select count(*) from atlas_kg.sample_category_result where sample_run_id=?", id).Scan(&catCount)
	db.Raw("select coalesce(sum(jsonb_array_length(raw_results)),0) from atlas_kg.sample_category_result where sample_run_id=?", id).Scan(&docCount)
	fmt.Printf("\n== raw extraction: %d category rows, %d documents ==\n", catCount, docCount)
}

func join(s []string) string {
	out := ""
	for i, v := range s {
		if i > 0 {
			out += ","
		}
		out += v
	}
	if out == "" {
		return "-"
	}
	return out
}

func inspect(db *gorm.DB) {
	queries := []string{
		"select 'sample_run', count(*) from atlas_kg.sample_run",
		"select 'sample_category_result', count(*) from atlas_kg.sample_category_result",
		"select 'sample_document_result', count(*) from atlas_kg.sample_document_result",
		"select 'gov_discovery', count(*) from atlas_kg.governance_record where kind='discovery'",
		"select 'gov_semantic_version', count(*) from atlas_kg.governance_record where kind='semantic-version'",
		"select 'extraction_run_total', count(*) from atlas_kg.extraction_run",
		"select 'extraction_run_succeeded', count(*) from atlas_kg.extraction_run where status='SUCCEEDED'",
		"select 'extraction_run_with_result', count(*) from atlas_kg.extraction_run where result is not null",
	}
	fmt.Println("-- counts --")
	for _, q := range queries {
		var name string
		var n int
		if err := db.Raw(q).Row().Scan(&name, &n); err != nil {
			fmt.Printf("  %s: error %v\n", q, err)
			continue
		}
		fmt.Printf("  %-32s %d\n", name, n)
	}

	fmt.Println("\n-- sample_run (latest 10) --")
	type sr struct {
		Id, Status     string
		Total, Current int
	}
	var srs []sr
	db.Raw("select id, status, total, current from atlas_kg.sample_run order by created_at desc limit 10").Scan(&srs)
	for _, s := range srs {
		fmt.Printf("  %s status=%s %d/%d\n", s.Id, s.Status, s.Current, s.Total)
	}

	fmt.Println("\n-- governance discovery (latest 10) --")
	type gr struct{ Id, Status, Version string }
	var grs []gr
	db.Raw("select id, status, version from atlas_kg.governance_record where kind='discovery' order by created_at desc limit 10").Scan(&grs)
	for _, g := range grs {
		fmt.Printf("  %s status=%s version=%s\n", g.Id, g.Status, g.Version)
	}

	fmt.Println("\n-- extraction_run by report_type (succeeded, has result) --")
	type rt struct {
		Type string
		N    int
	}
	var rts []rt
	db.Raw("select source_report_type, count(*) from atlas_kg.extraction_run where status='SUCCEEDED' and result is not null group by source_report_type order by 2 desc").Scan(&rts)
	for _, r := range rts {
		fmt.Printf("  %-20s %d\n", r.Type, r.N)
	}
}

func del(db *gorm.DB, all bool) {
	// sample_document_result has FK -> extraction_run (NO ACTION) and -> sample_run (CASCADE).
	// Delete children first, then sample_run, then governance. extraction_run last (optional).
	mustExec(db, "delete from atlas_kg.sample_document_result")
	mustExec(db, "delete from atlas_kg.sample_category_result")
	mustExec(db, "delete from atlas_kg.sample_run")
	mustExec(db, "delete from atlas_kg.governance_record where kind='discovery'")
	if all {
		mustExec(db, "delete from atlas_kg.extraction_run")
	}
	fmt.Println("delete done")
	var n int
	db.Raw("select count(*) from atlas_kg.extraction_run where result is not null").Scan(&n)
	fmt.Printf("extraction_run with result remaining: %d\n", n)
}

func mustExec(db *gorm.DB, sql string) {
	res := db.Exec(sql)
	if res.Error != nil {
		die("exec %q: %v", sql, res.Error)
	}
	fmt.Printf("  %-60s rows=%d\n", sql, res.RowsAffected)
}

func die(f string, args ...any) {
	fmt.Fprintf(os.Stderr, "dbtool: "+f+"\n", args...)
	os.Exit(1)
}
