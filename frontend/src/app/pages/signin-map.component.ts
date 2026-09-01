import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import * as L from 'leaflet';
import { LoginEvent } from '../core/models';
import { environment } from '../../environments/environment';

@Component({
  standalone: true,
  selector: 'st-signin-map',
  template: `<div class="signin-map" #host></div>`
})
export class SignInMapComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('host') host!: ElementRef<HTMLDivElement>;
  @Input() events: LoginEvent[] = [];
  private map?: L.Map;
  private layer?: L.LayerGroup;

  ngAfterViewInit(): void {
    const dark = document.documentElement.classList.contains('dark');
    const key = (window as Window & { __MAP_APIKEY?: string }).__MAP_APIKEY || environment.mapApiKey;
    const style = dark ? 'dark_all' : 'light_all';
    const tiles = `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png${key ? `?key=${encodeURIComponent(key)}` : ''}`;
    this.map = L.map(this.host.nativeElement, { scrollWheelZoom: false, worldCopyJump: true }).setView([20, 0], 2);
    L.tileLayer(tiles, { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>', subdomains: 'abcd', maxZoom: 18 }).addTo(this.map);
    this.layer = L.layerGroup().addTo(this.map);
    setTimeout(() => this.map?.invalidateSize(), 80);
    this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['events'] && this.map) this.render();
  }

  ngOnDestroy(): void { this.map?.remove(); }

  private render(): void {
    if (!this.map || !this.layer) return;
    this.layer.clearLayers();
    const points = this.events.filter(event => event.latitude != null && event.longitude != null) as Array<LoginEvent & { latitude: number; longitude: number }>;
    for (const event of points) {
      const color = event.succeeded ? '#72aa77' : '#bf5137';
      L.circleMarker([event.latitude, event.longitude], { radius: 7, color, fillColor: color, fillOpacity: .85, weight: 1 })
        .bindPopup(`${event.username}<br>${event.ipAddress}<br>${event.city ? event.city + ', ' : ''}${event.country ?? ''}<br>${event.succeeded ? 'Success' : 'Failed'}`)
        .addTo(this.layer);
    }
    if (points.length === 1) this.map.setView([points[0].latitude, points[0].longitude], 4);
    else if (points.length > 1) this.map.fitBounds(L.latLngBounds(points.map(event => [event.latitude, event.longitude])), { padding: [28, 28], maxZoom: 5 });
  }
}
