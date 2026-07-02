package classify

import (
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

var testRules = Rules{
	BossSenders:   []string{"boss@company.com"},
	FamilySenders: []string{"mom@family.pl"},
	ClientSenders: []string{"client.com"},
}

func TestClassify(t *testing.T) {
	c := UrgencyClassifier{Rules: testRules}
	cases := []struct {
		name  string
		email domain.Email
		want  domain.Priority
	}{
		{"boss sender is urgent", domain.Email{Sender: "Big Boss <boss@company.com>", Subject: "hi"}, domain.PriorityUrgent},
		{"boss match is case-insensitive", domain.Email{Sender: "BOSS@COMPANY.COM", Subject: "hi"}, domain.PriorityUrgent},
		{"family sender is urgent", domain.Email{Sender: "mom@family.pl", Subject: "obiad"}, domain.PriorityUrgent},
		{"deadline keyword is urgent", domain.Email{Sender: "x@y.com", Subject: "Project DEADLINE tomorrow"}, domain.PriorityUrgent},
		{"polish urgent keyword", domain.Email{Sender: "x@y.com", Subject: "Pilnie: dokumenty"}, domain.PriorityUrgent},
		{"security alert is urgent", domain.Email{Sender: "no-reply@bank.com", Subject: "Security alert on your account"}, domain.PriorityUrgent},
		{"client sender is important", domain.Email{Sender: "anna@client.com", Subject: "invoice"}, domain.PriorityImportant},
		{"promotions label is low", domain.Email{Sender: "shop@store.com", Subject: "sale", Labels: "INBOX,CATEGORY_PROMOTIONS"}, domain.PriorityLow},
		{"inbox+important labels", domain.Email{Sender: "x@y.com", Subject: "notes", Labels: "INBOX, IMPORTANT"}, domain.PriorityImportant},
		{"default is low", domain.Email{Sender: "x@y.com", Subject: "hello", Labels: "INBOX"}, domain.PriorityLow},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := c.Classify(tc.email); got != tc.want {
				t.Errorf("Classify(%q/%q) = %v, want %v", tc.email.Sender, tc.email.Subject, got, tc.want)
			}
		})
	}
}

func TestClassifyEmptyRulesNeverMatchIdentity(t *testing.T) {
	c := UrgencyClassifier{} // no senders configured
	got := c.Classify(domain.Email{Sender: "anyone@anywhere.com", Subject: "plain message"})
	if got != domain.PriorityLow {
		t.Errorf("empty rules: got %v, want LOW", got)
	}
}

func TestClassifyAllDoesNotMutateInput(t *testing.T) {
	c := UrgencyClassifier{Rules: testRules}
	in := []domain.Email{{ID: "1", Sender: "boss@company.com", Subject: "x"}}
	out := c.ClassifyAll(in)
	if in[0].Priority != "" {
		t.Error("input slice was mutated")
	}
	if out[0].Priority != domain.PriorityUrgent {
		t.Errorf("out[0].Priority = %v, want URGENT", out[0].Priority)
	}
}
