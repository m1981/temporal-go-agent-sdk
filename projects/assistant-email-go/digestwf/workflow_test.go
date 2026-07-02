package digestwf

import (
	"testing"

	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/testsuite"
)

func newEnv(t *testing.T) (*testsuite.TestWorkflowEnvironment, *Activities) {
	t.Helper()
	var ts testsuite.WorkflowTestSuite
	env := ts.NewTestWorkflowEnvironment()
	a := &Activities{}
	env.RegisterActivity(a.InQuietHours)
	env.RegisterActivity(a.RunDigestPipeline)
	env.RegisterActivity(a.RunAgentNarrative)
	return env, a
}

func TestDigestWorkflowSkipsDuringQuietHours(t *testing.T) {
	env, a := newEnv(t)
	env.OnActivity(a.InQuietHours, mock.Anything).Return(true, nil)

	env.ExecuteWorkflow(DigestWorkflow, Input{})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())
	var out Outcome
	require.NoError(t, env.GetWorkflowResult(&out))
	require.True(t, out.Skipped)
	env.AssertNotCalled(t, "RunDigestPipeline", mock.Anything, mock.Anything)
	env.AssertNotCalled(t, "RunAgentNarrative", mock.Anything)
}

func TestDigestWorkflowHappyPath(t *testing.T) {
	env, a := newEnv(t)
	env.OnActivity(a.InQuietHours, mock.Anything).Return(false, nil)
	env.OnActivity(a.RunDigestPipeline, mock.Anything,
		// Zero-valued Input must be defaulted by the workflow before the
		// activity sees it — that keeps Schedule payloads minimal.
		mock.MatchedBy(func(in Input) bool {
			return in.Query == defaultQuery && in.MaxResults == defaultMaxResults
		}),
	).Return(PipelineReport{Rendered: "# digest", Total: 3, UrgentCount: 1, NewUrgent: true}, nil)
	env.OnActivity(a.RunAgentNarrative, mock.Anything).Return("the narrative", nil)

	env.ExecuteWorkflow(DigestWorkflow, Input{})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())
	var out Outcome
	require.NoError(t, env.GetWorkflowResult(&out))
	require.False(t, out.Skipped)
	require.Equal(t, "the narrative", out.Narrative)
	require.True(t, out.Pipeline.NewUrgent)
	require.Equal(t, 3, out.Pipeline.Total)
}

func TestDigestWorkflowPropagatesPipelineFailure(t *testing.T) {
	env, a := newEnv(t)
	env.OnActivity(a.InQuietHours, mock.Anything).Return(false, nil)
	env.OnActivity(a.RunDigestPipeline, mock.Anything, mock.Anything).
		Return(PipelineReport{}, &CLIErrorStub{})

	env.ExecuteWorkflow(DigestWorkflow, Input{})

	require.True(t, env.IsWorkflowCompleted())
	require.Error(t, env.GetWorkflowError())
	env.AssertNotCalled(t, "RunAgentNarrative", mock.Anything)
}

// CLIErrorStub stands in for a gmail failure without importing the package.
type CLIErrorStub struct{}

func (*CLIErrorStub) Error() string { return "gmcli unavailable" }
