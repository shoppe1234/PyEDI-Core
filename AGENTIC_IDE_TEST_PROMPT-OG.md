# Agentic IDE Test Execution Prompt for PyEDI-Core

## Copy-Paste Prompt for Windsurf/Cascade/Cursor

```
I need you to perform a comprehensive code review and testing validation of my PyEDI-Core implementation (Phases 1-4). I have a complete testing specification document that defines exactly what needs to be validated.

PROJECT CONTEXT:
- GitHub Repository: [YOUR_REPO_URL_HERE]
- Branch: [main/dev/YOUR_BRANCH]
- Phases Completed: Phase 1 (Core Engine), Phase 2 (Library Interface), Phase 3 (REST API), Phase 4 (LLM Tools)
- Testing Specification: PyEDI_Core_Testing_Specification.md (attached/in project root)

YOUR OBJECTIVES:
1. Clone the repository and set up the Python environment
2. Verify the directory structure matches the specification
3. Run the complete test suite (unit, integration, user-supplied)
4. Generate coverage reports
5. Execute the code review checklist
6. Document all findings in TEST_RESULTS.md

STEP-BY-STEP EXECUTION PLAN:

PHASE 1: Environment Setup (15 minutes)
- Clone the repository from [YOUR_REPO_URL_HERE]
- Create and activate a Python virtual environment
- Install dependencies from pyproject.toml: `pip install -e .`
- Run the environment verification script from the testing spec
- Verify all required packages are installed
- Confirm directory structure matches spec (Section 2.3)

PHASE 2: Static Code Review (30 minutes)
- Review the "Code Review Checklist" section of the testing spec
- Check each item systematically:
  * No hardcoded transaction logic in .py files
  * error_handler.py called at every stage boundary
  * Config via Pydantic models only
  * correlation_id stamped on every log event
  * dry_run mode correct behavior
  * ThreadPoolExecutor max_workers configurable
  * schema_compiler hash check before recompile
- Document findings with file paths and line numbers

PHASE 3: Unit Tests (45 minutes)
- Run unit tests: `pytest tests/unit/ -v --tb=short`
- Generate coverage report: `pytest --cov=pyedi_core/core --cov-report=html`
- Open and review htmlcov/index.html
- Verify 85%+ coverage on core/ modules
- Document any failing tests with full traceback
- For each failure, analyze root cause

PHASE 4: Integration Tests - Standard Fixtures (1 hour)
- Check if standard test fixtures exist in tests/fixtures/
- If missing, create minimal fixtures based on spec examples
- Run: `pytest tests/integration/ -v --tb=long`
- Validate each test type:
  * Valid X12 810 processing
  * Valid CSV processing
  * Valid cXML processing
  * Malformed file routing to ./failed/
  * Duplicate detection
  * Unknown transaction fallback
  * Dry-run mode
- Document which tests pass/fail

PHASE 5: User-Supplied Data Tests (30 minutes - if applicable)
- Check if tests/user_supplied/ directory exists
- If exists, validate metadata.yaml format
- Run: `pytest tests/integration/test_user_supplied_data.py -v --tb=long`
- For any failures, compare actual vs expected output
- Document discrepancies with specific field-level details

PHASE 6: Library Interface Tests (30 minutes - if Phase 2 completed)
- Run: `pytest tests/integration/test_library_interface.py -v`
- Test: `python -c "from pyedi_core import Pipeline; print('Success')"`
- Validate PipelineResult structure
- Test return_payload option
- Document any import errors or structural issues

PHASE 7: API Tests (30 minutes - if Phase 3 completed)
- Start API server: `uvicorn api.app:app --reload` (in background)
- Run: `pytest tests/integration/test_api_endpoints.py -v`
- Test each endpoint manually with curl (commands in spec)
- Stop API server
- Document endpoint functionality and errors

PHASE 8: Manual Verification (30 minutes)
- Process a single file manually: `python main.py --config config/config.yaml`
- Verify output JSON structure (Section 8 of spec)
- Check manifest format in .processed file
- Test dry-run mode: `python main.py --config config/config.yaml --dry-run`
- Process the same file twice to verify duplicate detection
- Trigger an error case and verify ./failed/ directory and .error.json

PHASE 9: Results Documentation (30 minutes)
- Create TEST_RESULTS.md using the template in the testing spec
- Fill in all sections:
  * Summary (total tests, passed, failed, coverage %)
  * Phase 1 findings
  * Phase 2 findings
  * Phase 3 findings (if applicable)
  * Phase 4 findings (if applicable)
  * Code review findings with specific violations
  * Recommendations for fixes
- Attach or reference coverage report
- Include sample output JSON

DELIVERABLES:
1. TEST_RESULTS.md - Complete test results document
2. htmlcov/ - Coverage report directory
3. Summary of critical issues requiring immediate attention
4. List of passed vs failed checklist items
5. Recommendations for next steps

IMPORTANT NOTES:
- Follow the testing specification document EXACTLY
- Document EVERYTHING - even tests that pass
- For failures, provide specific file paths, line numbers, and error messages
- Compare all output JSON against the envelope structure in Section 8
- If any required files/directories are missing, note them but continue with what exists
- If Phase 3 or 4 don't exist yet, skip those sections but note it in results

CRITICAL SUCCESS CRITERIA (from spec Section 1):
✅ All non-negotiable implementation rules followed (Section 10.2 of spec)
✅ 85%+ test coverage on core/ modules
✅ All three drivers process fixture files successfully
✅ Error handling routes to ./failed/ with proper .error.json files
✅ dry-run mode validates without writing files
✅ Manifest deduplication works via SHA-256 hash
✅ PipelineResult model returns correct structure

Please begin with Phase 1 (Environment Setup) and proceed sequentially. After each phase, provide a brief summary before moving to the next phase. If you encounter any blockers, pause and ask for clarification.

Start now with: "Beginning PyEDI-Core testing execution. Phase 1: Environment Setup..."
```

---

## Alternative: Shorter "Quick Test" Prompt

If you want a faster initial validation:

```
Quick PyEDI-Core Validation:

1. Clone repo: [YOUR_REPO_URL]
2. Setup: `python -m venv venv && source venv/bin/activate && pip install -e .`
3. Run all tests: `pytest -v`
4. Generate coverage: `pytest --cov=pyedi_core/core --cov-report=html`
5. Manual test: `python main.py --config config/config.yaml --dry-run`
6. Review checklist from PyEDI_Core_Testing_Specification.md Section 9

Report:
- Test pass/fail count
- Coverage percentage
- Critical violations from checklist
- Top 3 issues to fix

Reference document: PyEDI_Core_Testing_Specification.md
```

---

## Alternative: "Fix Issues As You Find Them" Prompt

For a more iterative approach:

```
PyEDI-Core Test-Driven Validation with Auto-Fix:

You are performing code review and testing on PyEDI-Core implementation. Reference document is PyEDI_Core_Testing_Specification.md.

Repository: [YOUR_REPO_URL]

WORKFLOW:
1. Set up environment
2. Run pytest -v
3. For EACH failing test:
   - Analyze root cause
   - Propose fix
   - Wait for my approval
   - Implement fix
   - Re-run test
   - Confirm fix
4. Run coverage report
5. For EACH checklist violation in Section 9:
   - Show me the violation
   - Propose fix
   - Wait for my approval
   - Implement fix
6. Generate final TEST_RESULTS.md

IMPORTANT:
- Stop and get approval before making ANY code changes
- Show me the specific violation/failure first
- Explain what the fix will do
- Only proceed after I say "approved" or "fix it"

Start with: "Setting up environment for PyEDI-Core validation..."
```

---

## Customization Variables

Before using any prompt, replace these placeholders:

```
[YOUR_REPO_URL_HERE] → Your actual GitHub repository URL
[main/dev/YOUR_BRANCH] → The branch you want tested
[YOUR_REPO_URL] → Same as above
```

---

## Tips for Using with Agentic IDEs

### For Windsurf (Cascade):
1. Open your project in Windsurf
2. Open the Cascade panel
3. Paste the full prompt
4. Attach the PyEDI_Core_Testing_Specification.md file as context
5. Let it run through each phase

### For Cursor:
1. Open Composer (Cmd+K or Ctrl+K)
2. Select "Agent" mode
3. Paste the prompt
4. Reference the testing spec file with @PyEDI_Core_Testing_Specification.md
5. Monitor progress and approve changes

### For Aider:
1. Start aider in your repo: `aider`
2. Add relevant files: `/add pyedi_core/**/*.py tests/**/*.py`
3. Paste the prompt
4. Use `/run pytest` to execute tests
5. Use `/diff` to review proposed changes

### For Continue.dev:
1. Open VS Code with Continue extension
2. Select your entire project in the file explorer
3. Open Continue panel (Cmd+L)
4. Paste the prompt
5. Use the "Apply" button carefully for each suggested change

---

## Expected Timeline

| Phase | Duration | Can Run Parallel? |
|-------|----------|-------------------|
| Environment Setup | 15 min | No - must be first |
| Static Code Review | 30 min | No - needs code |
| Unit Tests | 45 min | No - needs env |
| Integration Tests | 1 hour | No - needs unit tests |
| User-Supplied Tests | 30 min | Yes - if data exists |
| Library Tests | 30 min | Yes - if Phase 2 done |
| API Tests | 30 min | Yes - if Phase 3 done |
| Manual Verification | 30 min | Yes - anytime |
| Documentation | 30 min | No - must be last |
| **TOTAL** | **4-5 hours** | |

---

## What to Expect from the Agent

The agent will:
1. ✅ Clone your repo and set up environment
2. ✅ Run all tests systematically
3. ✅ Generate coverage reports with HTML output
4. ✅ Check code against the specification
5. ✅ Document findings in structured format
6. ⚠️ May struggle with: Complex test failures, environment-specific issues
7. ⚠️ Will need help with: Access credentials, missing test data, ambiguous requirements

---

## Troubleshooting Common Issues

### "Can't find repository"
- Double-check your GitHub URL
- Ensure the agent has git access
- Try using HTTPS URL instead of SSH

### "Import errors during setup"
- Agent may need to install system dependencies (LibreOffice, pandoc)
- Check if pyproject.toml has all dependencies listed
- May need to run: `pip install badx12 pandas pyyaml pydantic structlog pytest`

### "Tests not found"
- Tests may not exist yet
- Ask agent to create minimal test structure first
- Point agent to the test examples in the specification

### "Coverage too low"
- Ask agent to identify which modules lack tests
- Request specific test creation for uncovered modules
- May need to adjust coverage target temporarily

---

## Post-Testing Actions

After the agent completes testing:

1. **Review TEST_RESULTS.md** - Read through findings carefully
2. **Check Coverage Report** - Open htmlcov/index.html in browser
3. **Prioritize Fixes** - Decide which issues to address first
4. **Create GitHub Issues** - For each critical finding
5. **Plan Remediation** - Estimate time to fix each issue
6. **Re-test After Fixes** - Run the agent again with fixes applied

---

## Success Indicators

You'll know testing was successful if:

✅ TEST_RESULTS.md exists and is complete
✅ Coverage report shows 85%+ on core/ modules
✅ All critical checklist items marked as passed
✅ Sample output JSONs match the specification envelope
✅ Manifest, error handling, and deduplication work correctly
✅ At least basic unit and integration tests pass

---

## Sample Agent Interaction

```
You: [paste full prompt]

Agent: Beginning PyEDI-Core testing execution. Phase 1: Environment Setup...
       Cloning repository from https://github.com/yourname/pyedi-core...
       Creating virtual environment...
       Installing dependencies...
       ✅ Environment setup complete. All packages installed.
       
       Phase 2: Static Code Review...
       Checking: No hardcoded transaction logic... ✅ PASS
       Checking: error_handler.py at stage boundaries... ⚠️ ISSUE FOUND
       - File: pyedi_core/drivers/csv_handler.py, Line 145
       - Issue: Transformation failure not calling error_handler
       - Recommendation: Add try/catch with error_handler.handle_failure()
       
       [continues through all phases...]

You: For the csv_handler.py issue - show me the exact code

Agent: [shows code snippet with context]
       
You: Approved - fix it

Agent: [makes the fix, commits, re-runs test]
       ✅ Fix applied and verified
       
       [continues to completion...]
       
Agent: Testing complete. TEST_RESULTS.md generated.
       Summary: 127 tests, 124 passed, 3 failed, 87% coverage
       Critical issues: 2
       Would you like me to address the failing tests?
```

---

**END OF PROMPT DOCUMENT**

Save this file and use the appropriate prompt based on your testing approach.
