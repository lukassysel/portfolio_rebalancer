import type { components } from './schema'

type S = components['schemas']
export type Snapshot = S['Snapshot']
export type Dataset = S['Dataset-Output']
export type Policy = S['Policy-Output']
export type EvaluationResult = S['EvaluationResult']
export type ClientResult = S['ClientResult']
export type Alternative = S['AlternativeOut']
export type Component = S['Component']
export type LotView = S['LotView']
export type Issue = S['Issue']
export type Meta = S['Meta']
