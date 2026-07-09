import type { ReactNode } from 'react'
import type { WorkflowStep } from '../../types'
import StepIndicator from '../common/StepIndicator'

interface WorkflowContainerProps {
  currentStep: WorkflowStep
  title: string
  description: string
  children: ReactNode
}

export default function WorkflowContainer({
  currentStep,
  title,
  description,
  children,
}: WorkflowContainerProps) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      {/* Header */}
      <div className="mb-8 text-center">
        <h2 className="font-display text-2xl font-bold text-ink tracking-tight">{title}</h2>
        <p className="mt-1.5 text-sm text-ink-muted">{description}</p>
      </div>

      {/* Step indicator */}
      <div className="mb-10">
        <StepIndicator currentStep={currentStep} />
      </div>

      {/* Content area */}
      <div>{children}</div>
    </div>
  )
}
