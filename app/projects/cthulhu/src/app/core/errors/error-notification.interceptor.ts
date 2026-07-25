import {HttpContextToken, HttpErrorResponse, HttpInterceptorFn} from '@angular/common/http';
import {inject} from '@angular/core';
import {ErrorNotificationService} from './error-notification.service';
import {catchError, throwError} from 'rxjs';

export const SKIP_GLOBAL_ERROR_NOTIFICATION = new HttpContextToken<boolean>(() => false);

export const errorNotificationInterceptor: HttpInterceptorFn = (req, next) => {
  const service = inject(ErrorNotificationService);
  return next(req).pipe(
    catchError(err => {
      if (err instanceof HttpErrorResponse && !req.context.get(SKIP_GLOBAL_ERROR_NOTIFICATION)) {
        service.addHttpError(err);
      }
      return throwError(() => err);
    })
  );
};
