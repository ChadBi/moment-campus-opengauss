import React, { useEffect, useState } from 'react';
import { Plus, MapPin, Check } from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import MapLocationPicker from './MapLocationPicker';
import { VerifyGate } from './VerifyGate';
import { useCampusStore } from '../store/useCampusStore';
import { useUIStore } from '../store/useUIStore';
import { categoriesApi, type CreateLocationRequest, type LocationListItem } from '../services/categories';
import { LOCATION_TYPE_OPTIONS, type LocationType } from '../constants/locationTypes';
import { buildLocationDescription } from '../utils/buildLocationDescription';

export interface CreateLocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (createdLocationId: number, createdLocation: LocationListItem) => void | Promise<void>;
}

const INITIAL_NAME = '';
const INITIAL_TYPE: LocationType | '' = '';
const INITIAL_DESCRIPTION = '';
const INITIAL_LAT = '';
const INITIAL_LNG = '';
const INITIAL_PICKED = false;
const PICKER_MODAL_INITIAL = false;
const SUBMIT_LOADING_INITIAL = false;

export const CreateLocationModal: React.FC<CreateLocationModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const [name, setName] = useState(INITIAL_NAME);
  const [type, setType] = useState<LocationType | ''>(INITIAL_TYPE);
  const [description, setDescription] = useState(INITIAL_DESCRIPTION);
  const [lat, setLat] = useState(INITIAL_LAT);
  const [lng, setLng] = useState(INITIAL_LNG);
  const [picked, setPicked] = useState(INITIAL_PICKED);
  const [pickerModalOpen, setPickerModalOpen] = useState(PICKER_MODAL_INITIAL);
  const [submitLoading, setSubmitLoading] = useState(SUBMIT_LOADING_INITIAL);

  const currentSchoolCenter = useCampusStore((s) => s.currentSchoolCenter);
  const showToast = useUIStore((s) => s.showToast);

  const resetAll = () => {
    setName(INITIAL_NAME);
    setType(INITIAL_TYPE);
    setDescription(INITIAL_DESCRIPTION);
    setLat(INITIAL_LAT);
    setLng(INITIAL_LNG);
    setPicked(INITIAL_PICKED);
    setPickerModalOpen(PICKER_MODAL_INITIAL);
    setSubmitLoading(SUBMIT_LOADING_INITIAL);
  };

  useEffect(() => {
    if (isOpen) {
      resetAll();
    }
  }, [isOpen]);

  const handlePick = (pickedLat: number, pickedLng: number) => {
    setLat(String(pickedLat));
    setLng(String(pickedLng));
    setPicked(true);
  };

  const confirmPicker = () => {
    setPickerModalOpen(false);
  };

  const closePicker = () => {
    setPickerModalOpen(false);
  };

  const handleSubmit = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      showToast('请填写地点名称', 'warning');
      return;
    }
    if (!picked) {
      showToast('请在地图上选择位置', 'warning');
      return;
    }
    const numLat = Number(lat);
    const numLng = Number(lng);
    if (
      !Number.isFinite(numLat) ||
      !Number.isFinite(numLng) ||
      numLat < -90 ||
      numLat > 90 ||
      numLng < -180 ||
      numLng > 180
    ) {
      showToast('坐标范围不合法', 'warning');
      return;
    }

    const payload: CreateLocationRequest = {
      name: trimmedName,
      latitude: numLat,
      longitude: numLng,
      description: buildLocationDescription(type, description),
    };

    try {
      setSubmitLoading(true);
      const created = await categoriesApi.createLocation(payload);
      showToast('地点已提交，等待核验', 'success');
      resetAll();
      onClose();
      if (onCreated) {
        await onCreated(created.id, created);
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      const detail = axiosErr?.response?.data?.detail;
      showToast(detail || '新增地点失败', 'error');
    } finally {
      setSubmitLoading(false);
    }
  };

  const badgeText = picked
    ? `已选位置 · ${Number(lat).toFixed(5)}, ${Number(lng).toFixed(5)}`
    : '尚未选择位置';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="新增地点" size="lg">
      <VerifyGate message="完成校园身份认证后即可新增地点" compact>
        <div className="space-y-5">
          <div className="rounded-[12px] border border-line bg-paper-hover/40 p-4">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <MapPin size={16} className="text-lamp flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-ink">地图选点</p>
                  <span
                    className={`inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-md text-xs ${
                      picked
                        ? 'bg-grass/10 text-grass border border-grass/20'
                        : 'bg-mist/60 text-ink-sub border border-line/60'
                    }`}
                  >
                    {picked ? <Check size={11} /> : null}
                    {badgeText}
                  </span>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                icon={<MapPin size={14} />}
                onClick={() => setPickerModalOpen(true)}
              >
                在地图上选择位置
              </Button>
            </div>
          </div>

          <Input
            label="地点名称"
            required
            placeholder="例如：图书馆南门、第一食堂三楼"
            value={name}
            maxLength={60}
            onChange={(e) => setName(e.target.value)}
          />

          <div className="w-full">
            <label className="block text-sm font-medium text-ink mb-1.5 font-sans">
              场所类型
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as LocationType | '')}
              className="w-full h-10 px-3.5 bg-paper border border-line rounded-[10px] text-[14px] text-ink transition-[background-color,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus:border-lake"
            >
              <option value="">请选择场所类型</option>
              {LOCATION_TYPE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          <div className="w-full">
            <label className="block text-sm font-medium text-ink mb-1.5 font-sans">
              描述
            </label>
            <textarea
              value={description}
              maxLength={480}
              placeholder="可选：补充楼层、入口、营业时间等说明信息（最多 480 字）"
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full px-3.5 py-2.5 bg-paper border border-line rounded-[10px] text-[14px] text-ink placeholder:text-ink-muted/60 transition-[background-color,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus:border-lake resize-none font-sans"
            />
            <div className="mt-1 text-right text-xs text-ink-muted">
              {description.length}/480
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2 border-t border-ink-divider">
            <Button variant="text" size="sm" onClick={onClose} disabled={submitLoading}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus size={14} />}
              loading={submitLoading}
              onClick={handleSubmit}
            >
              提交新增地点
            </Button>
          </div>
        </div>
      </VerifyGate>

      <Modal isOpen={pickerModalOpen} onClose={closePicker} title="在地图上选择位置" size="lg">
        <div className="space-y-4">
          <MapLocationPicker
            initialLat={picked && lat ? Number(lat) : currentSchoolCenter?.lat}
            initialLng={picked && lng ? Number(lng) : currentSchoolCenter?.lng}
            onPick={handlePick}
            height={360}
          />
          <div className="flex items-center justify-end gap-3 pt-2 border-t border-ink-divider">
            <Button variant="text" size="sm" onClick={closePicker}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Check size={14} />}
              onClick={confirmPicker}
              disabled={!picked}
            >
              确认选点
            </Button>
          </div>
        </div>
      </Modal>
    </Modal>
  );
};

export default CreateLocationModal;
