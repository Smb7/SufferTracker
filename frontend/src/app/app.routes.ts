import { inject } from '@angular/core';
import { Routes } from '@angular/router';
import { AuthService } from './core/auth.service';
import { authGuard } from './core/auth.guard';
import { AppShellComponent } from './layout/app-shell.component';
import { DemoComponent } from './pages/demo.component';
import { LoginComponent } from './pages/login.component';
import { DashboardComponent } from './pages/dashboard.component';
import { JobsComponent } from './pages/jobs.component';
import { SettingsComponent } from './pages/settings.component';

const authenticatedMatch = () => inject(AuthService).token !== null;

export const routes: Routes = [
  { path: '', canMatch: [authenticatedMatch], component: AppShellComponent, canActivate: [authGuard], children: [
    { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    { path: 'dashboard', component: DashboardComponent },
    { path: 'jobs', component: JobsComponent },
    { path: 'settings', component: SettingsComponent }
  ]},
  { path: '', component: DemoComponent, pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: '**', redirectTo: '' }
];
