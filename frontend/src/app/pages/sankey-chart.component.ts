import { Component, Input } from '@angular/core';
import { ChartJob, sankeyLayout } from '../core/chart-data';

@Component({
  standalone: true,
  selector: 'st-sankey',
  template: `
    <svg class="sankey-figure" [attr.viewBox]="'0 0 ' + layout.width + ' ' + layout.height" role="img" [attr.aria-label]="ariaLabel">
      @for (ribbon of layout.ribbons; track $index) {
        <path [attr.d]="ribbon.d" [attr.fill]="ribbon.color" class="sankey-link"/>
      }
      @for (node of layout.nodes; track node.label) {
        <g>
          <rect [attr.x]="node.x" [attr.y]="node.y" [attr.width]="node.w" [attr.height]="node.h" rx="2" [attr.fill]="node.color"/>
          <text [attr.x]="node.labelX" [attr.y]="node.countY" [attr.text-anchor]="node.anchor" class="sankey-count">{{ node.count }}</text>
          <text [attr.x]="node.labelX" [attr.y]="node.labelY" [attr.text-anchor]="node.anchor" class="sankey-label">{{ node.label }}</text>
        </g>
      }
    </svg>
  `
})
export class SankeyChartComponent {
  @Input() jobs: ChartJob[] = [];
  @Input() interviewRounds = 3;
  @Input() ariaLabel = 'Application flow sankey diagram';
  get layout() { return sankeyLayout(this.jobs, this.interviewRounds); }
}
