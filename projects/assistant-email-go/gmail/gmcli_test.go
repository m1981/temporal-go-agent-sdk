package gmail

import (
	"context"
	"errors"
	"testing"
)

const sampleOutput = "ID\tDate\tFrom\tSubject\tLabels\n" +
	"abc123\t2026-07-01\tboss@x.com\tHello there\tINBOX,IMPORTANT\n" +
	"def456\t2026-07-01\tshop@y.com\tSale!\tCATEGORY_PROMOTIONS\n" +
	"malformed row without tabs\n" +
	"# Next page: some-token\n"

func fakeClient(out string, err error, captured *[]string) *Client {
	return &Client{
		UserEmail: "me@example.com",
		Runner: func(_ context.Context, name string, args ...string) (string, error) {
			if captured != nil {
				*captured = append([]string{name}, args...)
			}
			return out, err
		},
	}
}

func TestSearchParsesRows(t *testing.T) {
	var got []string
	c := fakeClient(sampleOutput, nil, &got)
	emails, err := c.Search(context.Background(), "newer_than:2h", 50)
	if err != nil {
		t.Fatalf("Search: %v", err)
	}
	if len(emails) != 2 {
		t.Fatalf("len = %d, want 2 (header, malformed, footer skipped)", len(emails))
	}
	if emails[0].ID != "abc123" || emails[0].Sender != "boss@x.com" || emails[0].Labels != "INBOX,IMPORTANT" {
		t.Errorf("first row parsed wrong: %+v", emails[0])
	}
	want := []string{"gmcli", "me@example.com", "search", "newer_than:2h", "--max", "50"}
	if len(got) != len(want) {
		t.Fatalf("cmd = %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("cmd = %v, want %v", got, want)
		}
	}
}

func TestSearchEmptyOutput(t *testing.T) {
	c := fakeClient("ID\tDate\tFrom\tSubject\tLabels\n", nil, nil)
	emails, err := c.Search(context.Background(), "q", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(emails) != 0 {
		t.Errorf("want no emails, got %v", emails)
	}
}

func TestRunnerErrorBecomesCLIError(t *testing.T) {
	c := fakeClient("", errors.New("exit status 1: auth expired"), nil)
	_, err := c.Search(context.Background(), "q", 10)
	var cliErr *CLIError
	if !errors.As(err, &cliErr) {
		t.Fatalf("want *CLIError, got %T: %v", err, err)
	}
}

func TestThreadRequiresID(t *testing.T) {
	c := fakeClient("body", nil, nil)
	if _, err := c.Thread(context.Background(), ""); err == nil {
		t.Fatal("want error for empty thread id")
	}
}

func TestSendBuildsArgs(t *testing.T) {
	var got []string
	c := fakeClient("sent", nil, &got)
	out, err := c.Send(context.Background(), "to@x.com", "Subj", "Body", "thr-1")
	if err != nil || out != "sent" {
		t.Fatalf("Send: %q, %v", out, err)
	}
	want := []string{"gmcli", "me@example.com", "send", "--to", "to@x.com",
		"--subject", "Subj", "--body", "Body", "--thread", "thr-1"}
	if len(got) != len(want) {
		t.Fatalf("cmd = %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("cmd = %v, want %v", got, want)
		}
	}
}
