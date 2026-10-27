// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { ReservationRequest, ReservationStatus } from '../domain/recovery/contracts.ts';
import { reject } from './contracts.ts';
import { canonical, one, rows } from './schema.ts';
const KEY='storage.reservations/1';
interface Journal { active: Record<string,{intentId:string;peakBytes:number}>; debt:Record<string,number> }
function read(db:DatabaseSync):Journal { const row=one(db,'SELECT value FROM preferences WHERE key=?',KEY);return row?JSON.parse(String(row.value)):{active:{},debt:{}}; }
function write(db:DatabaseSync,j:Journal) { db.prepare('INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at').run(KEY,canonical(j),new Date().toISOString()); }
function status(j:Journal):ReservationStatus {return {reservedBytes:Object.values(j.active).reduce((n,r)=>n+r.peakBytes,0),cleanupDebtBytes:Object.values(j.debt).reduce((n,b)=>n+b,0),reservations:Object.keys(j.active).length};}
export function reservationStatus(db:DatabaseSync) { return status(read(db)); }
export function reserveStorage(db:DatabaseSync,r:ReservationRequest) {
  const j=read(db), old=j.active[r.id];
  if(old) {if(old.intentId!==r.intentId||old.peakBytes!==r.peakBytes)reject('storage_reservation_conflict');return status(j);}
  if(Object.keys(j.active).length>=64)reject('storage_reservation_capacity');
  const held=status(j), charge=held.reservedBytes+held.cleanupDebtBytes+r.peakBytes;
  if(r.allocatedBytes+charge>r.ceilingBytes||r.freeBytes-charge<12*1024**3)reject('storage_waiting_space');
  j.active[r.id]={intentId:r.intentId,peakBytes:r.peakBytes};write(db,j);return status(j);
}
export function settleStorage(db:DatabaseSync,id:string,intentId:string,settled:boolean,cleanupDebtBytes:number) {
  const j=read(db),r=j.active[id];if(!r||r.intentId!==intentId)reject('storage_reservation_missing');
  if(!settled)return status(j);delete j.active[id];if(cleanupDebtBytes)j.debt[id]=cleanupDebtBytes;write(db,j);return status(j);
}
