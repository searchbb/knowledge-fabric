// Live review provider — wraps services/api/reviewApi reads.

import { getReviewView as apiGetReviewView } from '../../../services/api/reviewApi'

export function getReviewView(projectId) {
  return apiGetReviewView(projectId)
}
