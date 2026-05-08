import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzUploadModule, NzUploadFile } from 'ng-zorro-antd/upload';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { AtlasApiService, DocumentItem } from '../services/atlas-api.service';

@Component({
  selector: 'app-document-management',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzCardModule, NzTableModule, NzTagModule,
    NzSpinModule, NzEmptyModule, NzIconModule, NzButtonModule,
    NzUploadModule, NzSelectModule, NzInputModule, NzModalModule,
  ],
  template: `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <!-- Upload & Filter -->
      <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
          <button nz-button nzType="primary" nzSize="small" (click)="showUpload = true">
            <span nz-icon nzType="upload"></span> Upload Document
          </button>
          <nz-select [(ngModel)]="filterDocType" nzPlaceHolder="Doc Type" nzSize="small"
            nzAllowClear style="width: 140px;" (ngModelChange)="loadDocuments()">
            @for (t of docTypes; track t) {
              <nz-option [nzValue]="t" [nzLabel]="t"></nz-option>
            }
          </nz-select>
          <nz-select [(ngModel)]="filterStatus" nzPlaceHolder="Status" nzSize="small"
            nzAllowClear style="width: 120px;" (ngModelChange)="loadDocuments()">
            <nz-option nzValue="pending" nzLabel="Pending"></nz-option>
            <nz-option nzValue="completed" nzLabel="Processed"></nz-option>
          </nz-select>
          <button nz-button nzSize="small" (click)="loadDocuments()">
            <span nz-icon nzType="reload"></span> Refresh
          </button>
        </div>
      </nz-card>

      <!-- Document list -->
      <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        @if (loading) {
          <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
        } @else if (documents.length > 0) {
          <nz-table #docTable [nzData]="documents" nzSize="small" [nzShowPagination]="false"
            [nzScroll]="{ y: '500px' }" nzFrontPagination="false">
            <thead><tr>
              <th nzWidth="120px">Doc ID</th>
              <th>Title</th>
              <th nzWidth="90px">Type</th>
              <th nzWidth="100px">Source</th>
              <th nzWidth="100px">Company</th>
              <th nzWidth="80px">Status</th>
              <th nzWidth="90px">Created</th>
              <th nzWidth="80px">Actions</th>
            </tr></thead>
            <tbody>
              @for (d of docTable.data; track d.doc_id) {
                <tr>
                  <td style="font-size: 11px; font-family: monospace;">{{ d.doc_id }}</td>
                  <td style="font-size: 12px;">{{ d.title }}</td>
                  <td><nz-tag [nzColor]="getDocTypeColor(d.doc_type)" style="font-size: 10px;">{{ d.doc_type }}</nz-tag></td>
                  <td style="font-size: 11px;">{{ d.source_type }}</td>
                  <td style="font-size: 12px;">{{ d.company || '-' }}</td>
                  <td>
                    <nz-tag [nzColor]="d.processed ? 'green' : 'orange'" style="font-size: 10px;">
                      {{ d.processed ? 'Done' : 'Pending' }}
                    </nz-tag>
                  </td>
                  <td style="font-size: 11px; color: #999;">{{ (d.created_at || '').substring(0, 10) }}</td>
                  <td>
                    @if (!d.processed) {
                      <button nz-button nzType="link" nzSize="small" [nzLoading]="extractingId === d.doc_id"
                        (click)="extractDoc(d.doc_id)">
                        <span nz-icon nzType="experiment"></span>
                      </button>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </nz-table>
        } @else {
          <nz-empty nzNotFoundContent="No documents found"></nz-empty>
        }
      </nz-card>

      <!-- Upload Modal -->
      <nz-modal [(nzVisible)]="showUpload" nzTitle="Upload Document" (nzOnCancel)="showUpload = false"
        (nzOnOk)="submitUpload()" [nzOkLoading]="uploading" nzOkText="Upload">
        <ng-container *nzModalContent>
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <div>
              <label style="font-size: 12px; color: #666;">Document Type *</label>
              <nz-select [(ngModel)]="uploadDocType" nzSize="small" style="width: 100%;">
                @for (t of docTypes; track t) {
                  <nz-option [nzValue]="t" [nzLabel]="t"></nz-option>
                }
              </nz-select>
            </div>
            <div>
              <label style="font-size: 12px; color: #666;">Company (optional)</label>
              <input nz-input [(ngModel)]="uploadCompany" nzSize="small" />
            </div>
            <div>
              <label style="font-size: 12px; color: #666;">File</label>
              <nz-upload [nzBeforeUpload]="beforeUpload" [nzFileList]="fileList">
                <button nz-button nzSize="small">
                  <span nz-icon nzType="upload"></span> Select File
                </button>
              </nz-upload>
            </div>
          </div>
        </ng-container>
      </nz-modal>
    </div>
  `,
})
export class DocumentManagementComponent implements OnInit {
  private api = inject(AtlasApiService);
  private msg = inject(NzMessageService);

  documents: DocumentItem[] = [];
  loading = false;
  filterDocType = '';
  filterStatus = '';
  extractingId = '';

  // Upload
  showUpload = false;
  uploading = false;
  uploadDocType = 'manual';
  uploadCompany = '';
  fileList: NzUploadFile[] = [];

  docTypes = ['earnings', 'research', 'industry', 'news', 'policy', 'announcement', 'manual'];

  beforeUpload = (file: NzUploadFile): boolean => {
    this.fileList = [file];
    return false; // Prevent auto-upload
  };

  ngOnInit(): void {
    this.loadDocuments();
  }

  loadDocuments(): void {
    this.loading = true;
    this.api.listDocuments({
      doc_type: this.filterDocType,
      status: this.filterStatus,
      limit: 100,
    }).subscribe({
      next: (r) => { this.documents = r.documents || []; this.loading = false; },
      error: () => { this.msg.error('Failed to load documents'); this.loading = false; },
    });
  }

  submitUpload(): void {
    if (this.fileList.length === 0) {
      this.msg.warning('Please select a file');
      return;
    }
    this.uploading = true;
    const file = this.fileList[0] as any;
    this.api.uploadDocument(file, this.uploadDocType, this.uploadCompany).subscribe({
      next: () => {
        this.msg.success('Document uploaded');
        this.uploading = false;
        this.showUpload = false;
        this.fileList = [];
        this.loadDocuments();
      },
      error: () => { this.msg.error('Upload failed'); this.uploading = false; },
    });
  }

  extractDoc(docId: string): void {
    this.extractingId = docId;
    this.api.extractDocument(docId).subscribe({
      next: (r) => {
        this.msg.success(`Extracted: ${r.chunks_processed || 0} chunks, ${r.nodes_created || 0} nodes`);
        this.extractingId = '';
        this.loadDocuments();
      },
      error: () => { this.msg.error('Extraction failed'); this.extractingId = ''; },
    });
  }

  getDocTypeColor(t: string): string {
    const colors: Record<string, string> = {
      earnings: 'blue', research: 'purple', industry: 'cyan', news: 'orange',
      policy: 'magenta', announcement: 'geekblue', manual: 'default',
    };
    return colors[t] || 'default';
  }
}

