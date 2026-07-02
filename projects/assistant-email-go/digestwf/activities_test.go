package digestwf

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

type fakeGmail struct {
	emails []domain.Email
}

func (f *fakeGmail) Search(context.Context, string, int) ([]domain.Email, error) {
	return f.emails, nil
}
func (f *fakeGmail) Thread(context.Context, string) (string, error) { return "", nil }
func (f *fakeGmail) Send(context.Context, string, string, string, string) (string, error) {
	return "", nil
}

func TestInQuietHoursUsesSettings(t *testing.T) {
	always := &Activities{Settings: &config.Settings{QuietHours: config.QuietHours{Start: 0, End: 23}}}
	never := &Activities{Settings: &config.Settings{QuietHours: config.QuietHours{Start: 5, End: 5}}}

	if time.Now().Hour() != 23 { // window covers 00-23, so only 23:xx is outside
		got, err := always.InQuietHours(context.Background())
		if err != nil || !got {
			t.Errorf("InQuietHours(00-23) = %v, %v; want true", got, err)
		}
	}
	got, err := never.InQuietHours(context.Background())
	if err != nil || got {
		t.Errorf("InQuietHours(disabled) = %v, %v; want false", got, err)
	}
}

func TestRunDigestPipelineProducesReport(t *testing.T) {
	a := &Activities{
		Settings: &config.Settings{
			MemoryPath: filepath.Join(t.TempDir(), "m.sqlite"),
		},
		Gmail: &fakeGmail{emails: []domain.Email{
			{ID: "u1", Sender: "x@y.com", Subject: "URGENT: deadline today"},
			{ID: "l1", Sender: "shop@z.com", Subject: "sale", Labels: "CATEGORY_PROMOTIONS"},
		}},
	}

	report, err := a.RunDigestPipeline(context.Background(), Input{Query: "q", MaxResults: 10})
	if err != nil {
		t.Fatal(err)
	}
	if report.Total != 2 || report.UrgentCount != 1 || !report.NewUrgent {
		t.Errorf("report = %+v, want total 2, urgent 1, new urgent", report)
	}
	if len(report.NewThreadIDs) != 2 {
		t.Errorf("NewThreadIDs = %v, want both", report.NewThreadIDs)
	}
	if report.Rendered == "" {
		t.Error("rendered digest is empty")
	}
}
