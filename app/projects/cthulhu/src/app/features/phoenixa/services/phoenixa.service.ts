import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {WriteBufferStatus} from '../models/phoenixa.models';
import {environment} from '../../../../environments/environment';

const BASE_URL = environment.phoenixAApiBase;

@Injectable({
  providedIn: 'root'
})
export class PhoenixAService {
  private http = inject(HttpClient);

  getBufferStats(): Observable<WriteBufferStatus> {
    return this.http.get<WriteBufferStatus>(`${BASE_URL}/api/v2/buffer/stats`);
  }
}

