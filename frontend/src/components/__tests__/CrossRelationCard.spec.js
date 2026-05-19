import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CrossRelationCard from '../CrossRelationCard.vue'

describe('CrossRelationCard', () => {
  it('labels the adjacent concept source article instead of rendering it as an unlabeled tag', () => {
    const wrapper = mount(CrossRelationCard, {
      props: {
        currentEntryId: 'entry_fde',
        conceptMap: {
          entry_fde: { canonical_name: 'FDE 模式', source_links: [] },
          entry_ai_change: {
            canonical_name: '技术从来不是 AI 转型最难的部分',
            source_links: [
              { project_id: 'proj_article', project_name: '正式裁减30000人，赔偿N+4', concept_key: 'Principle:ai-change' },
            ],
          },
        },
        relation: {
          relation_id: 'rel_1',
          source_entry_id: 'entry_ai_change',
          target_entry_id: 'entry_fde',
          relation_type: 'capability_constraint',
          directionality: 'directed',
          reason: 'FDE depends on non-technical adoption work.',
          confidence: 0.92,
          source: 'auto',
          review_status: 'unreviewed',
          evidence_refs: [],
        },
      },
    })

    const articleTag = wrapper.find('.xrel-article-tag')

    expect(articleTag.text()).toBe('来源文章《正式裁减30000人，赔偿N+4》')
    expect(articleTag.attributes('title')).toBe('打开相邻概念来源文章：正式裁减30000人，赔偿N+4')
    expect(articleTag.attributes('href')).toBe(
      '/workspace/proj_article/article?view=reading&focusNode=Principle%3Aai-change&from=registry',
    )
    expect(wrapper.text()).toContain('FDE 模式')
    expect(wrapper.text()).toContain('技术从来不是 AI 转型最难的部分')
  })

  it('routes source evidence jumps to the workspace article graph with focus context', async () => {
    const wrapper = mount(CrossRelationCard, {
      props: {
        currentEntryId: 'entry_a',
        conceptMap: {
          entry_a: { canonical_name: 'Source Concept', source_links: [] },
          entry_b: {
            canonical_name: 'Target Concept',
            source_links: [
              { project_id: 'proj_target', project_name: 'Target Project', concept_key: 'Topic:target-node' },
            ],
          },
        },
        relation: {
          relation_id: 'rel_1',
          source_entry_id: 'entry_a',
          target_entry_id: 'entry_b',
          relation_type: 'problem_solution',
          directionality: 'directed',
          reason: 'Links two concepts.',
          confidence: 0.82,
          source: 'llm',
          review_status: 'accepted',
          evidence_refs: [
            {
              project_id: 'proj_source',
              project_name: 'Source Project',
              concept_key: 'Problem:source-node',
              source_text: 'A source node summary.',
            },
          ],
        },
      },
    })

    await wrapper.findAll('button').find((button) => button.text().includes('展开详情')).trigger('click')

    expect(wrapper.find('.xrel-ref-jump').attributes('href')).toBe(
      '/workspace/proj_source/article?view=reading&focusNode=Problem%3Asource-node&from=registry',
    )
    expect(wrapper.find('.btn-primary').attributes('href')).toBe(
      '/workspace/proj_target/article?view=reading&focusNode=Topic%3Atarget-node&from=registry',
    )
  })

  it('emits relation type edits without hiding review actions', async () => {
    const wrapper = mount(CrossRelationCard, {
      props: {
        currentEntryId: 'entry_a',
        conceptMap: {
          entry_a: { canonical_name: 'Source Concept', source_links: [] },
          entry_b: { canonical_name: 'Target Concept', source_links: [] },
        },
        relation: {
          relation_id: 'rel_1',
          source_entry_id: 'entry_a',
          target_entry_id: 'entry_b',
          relation_type: 'problem_solution',
          directionality: 'directed',
          reason: 'Links two concepts.',
          confidence: 0.82,
          source: 'llm',
          review_status: 'unreviewed',
          evidence_refs: [],
        },
      },
    })

    await wrapper.findAll('button').find((button) => button.text().includes('展开详情')).trigger('click')
    await wrapper.find('.xrel-type-select').setValue('supports')
    await wrapper.findAll('button').find((button) => button.text() === '保存类型').trigger('click')

    expect(wrapper.emitted('type-change')[0]).toEqual(['rel_1', 'supports'])
    expect(wrapper.text()).toContain('关系类型已更新')
    expect(wrapper.text()).toContain('接受')
    expect(wrapper.text()).toContain('驳回')
  })
})
