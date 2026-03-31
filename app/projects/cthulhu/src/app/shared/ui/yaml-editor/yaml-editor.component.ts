import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild
} from '@angular/core';
import {CommonModule} from '@angular/common';

import {Compartment, EditorState} from '@codemirror/state';
import {
  crosshairCursor,
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
  rectangularSelection
} from '@codemirror/view';
import {defaultKeymap, history, historyKeymap, indentWithTab} from '@codemirror/commands';
import {
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  foldKeymap,
  indentOnInput,
  syntaxHighlighting
} from '@codemirror/language';
import {yaml as yamlLanguage} from '@codemirror/lang-yaml';

@Component({
  selector: 'app-yaml-editor',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="yaml-editor" #host></div>
  `,
  styles: [
    `
      .yaml-editor {
        border: 1px solid #f0f0f0;
        border-radius: 6px;
        overflow: hidden;
      }
      .yaml-editor :host {
        display: block;
      }
    `
  ]
})
export class YamlEditorComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('host', {static: true}) hostRef!: ElementRef<HTMLDivElement>;

  @Input() value = '';
  @Input() minHeightPx = 600;
  @Input() readOnly = false;

  @Output() valueChange = new EventEmitter<string>();

  private view?: EditorView;
  private suppressEmit = false;
  private editableCompartment = new Compartment();

  ngAfterViewInit(): void {
    this.createView();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.view) return;

    if (changes['readOnly']) {
      this.view.dispatch({
        effects: this.editableCompartment.reconfigure(EditorView.editable.of(!this.readOnly))
      });
    }

    if (changes['value']) {
      const current = this.view.state.doc.toString();
      if (this.value !== current) {
        this.suppressEmit = true;
        this.view.dispatch({
          changes: {from: 0, to: current.length, insert: this.value}
        });
        this.suppressEmit = false;
      }
    }
  }

  ngOnDestroy(): void {
    this.view?.destroy();
  }

  private createView() {
    const updateListener = EditorView.updateListener.of(update => {
      if (!update.docChanged || this.suppressEmit) return;
      this.valueChange.emit(update.state.doc.toString());
    });

    const theme = EditorView.theme({
      '&': {
        fontFamily: "Consolas, Monaco, 'Courier New', monospace",
        fontSize: '14px',
        lineHeight: '1.5',
        minHeight: `${this.minHeightPx}px`
      }
    });

    const state = EditorState.create({
      doc: this.value ?? '',
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightSpecialChars(),
        history(),
        foldGutter(), // folding UI
        drawSelection(),
        dropCursor(),
        indentOnInput(),
        bracketMatching(),
        rectangularSelection(),
        crosshairCursor(),
        syntaxHighlighting(defaultHighlightStyle, {fallback: true}),
        yamlLanguage(),
        keymap.of([
          indentWithTab,
          ...defaultKeymap,
          ...historyKeymap,
          ...foldKeymap
        ]),
        EditorView.lineWrapping,
        this.editableCompartment.of(EditorView.editable.of(!this.readOnly)),
        updateListener,
        theme
      ]
    });

    this.view = new EditorView({
      state,
      parent: this.hostRef.nativeElement
    });
  }
}
