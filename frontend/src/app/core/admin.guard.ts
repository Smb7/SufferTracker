import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const adminGuard: CanActivateFn = () => inject(AuthService).user()?.isAdmin ? true : inject(Router).createUrlTree(['/dashboard']);
