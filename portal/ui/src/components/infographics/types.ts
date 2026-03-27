export interface InfographicThemeProps {
  onNavigate?: (page: string) => void
}

export interface WorkflowStep {
  pageKey: string
  title: string
  subtitle: string
}

export interface CLICommand {
  command: string
  description: string
}

export interface QuickTip {
  label: string
  text: string
  pageKey: string
}

export const WORKFLOW_STEPS: WorkflowStep[] = [
  { pageKey: 'validate', title: 'Validate', subtitle: 'Compile your DSL schema' },
  { pageKey: 'onboard', title: 'Onboard', subtitle: 'Register partner & configure rules' },
  { pageKey: 'compare', title: 'Compare', subtitle: 'Run field-by-field comparisons' },
  { pageKey: 'rules', title: 'Rules', subtitle: 'Manage severity tiers (hard/soft/ignore)' },
  { pageKey: 'pipeline', title: 'Pipeline', subtitle: 'View processing results & status' },
]

export const CLI_COMMANDS: CLICommand[] = [
  { command: 'python -m pycoreedi validate <schema.dsl>', description: 'Compile & validate a DSL schema file' },
  { command: 'python -m pycoreedi run <config.yaml>', description: 'Run the full processing pipeline' },
  { command: 'python -m pycoreedi compare <source> <target>', description: 'Compare two files field-by-field' },
]

export const QUICK_TIPS: QuickTip[] = [
  { label: 'Start Here', text: 'Upload your DSL schema on the Validate page to compile it into YAML', pageKey: 'validate' },
  { label: 'New Partner?', text: 'Use the Onboard wizard to register and configure in 3 steps', pageKey: 'onboard' },
  { label: 'Pro Tip', text: 'Set up rule tiers (hard/soft/ignore) before running comparisons', pageKey: 'rules' },
  { label: 'Check Results', text: 'The Pipeline page shows all processing runs with status tracking', pageKey: 'pipeline' },
]
