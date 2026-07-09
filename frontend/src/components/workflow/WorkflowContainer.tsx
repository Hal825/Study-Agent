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
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      </div>

      {/* Step indicator */}
      <div className="mb-10">
        <StepIndicator currentStep={currentStep} />
      </div>

      {/* Step content */}
      <div className="min-h-[300px]">{children}</div>
    </div>
  )
}
