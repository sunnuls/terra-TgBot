import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ChevronRight, ChevronDown, Users } from "lucide-react";
import { api } from "../api/client";
import { toast } from "../components/Toast";

interface Group {
  id: number;
  name: string;
  parent_id: number | null;
  member_count: number;
  children: Group[];
}

interface Member {
  user_id: number;
  group_id: number;
  role: string | null;
  full_name: string | null;
  username: string | null;
}

export default function GroupsPage() {
  const qc = useQueryClient();
  const [newGroupName, setNewGroupName] = useState("");
  const [selectedParent, setSelectedParent] = useState<number | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [addMemberId, setAddMemberId] = useState("");

  const { data: groups = [], isLoading } = useQuery<Group[]>({
    queryKey: ["groups"],
    queryFn: () => api.get("/groups").then((r) => r.data),
  });

  const { data: members = [] } = useQuery<Member[]>({
    queryKey: ["group-members", selectedGroup?.id],
    queryFn: () => api.get(`/groups/${selectedGroup!.id}/members`).then((r) => r.data),
    enabled: !!selectedGroup,
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; parent_id: number | null }) => api.post("/groups", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      setNewGroupName("");
      toast("success", "Группа создана");
    },
    onError: (e: any) => toast("error", e?.response?.data?.detail || "Ошибка создания группы"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/groups/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      setSelectedGroup(null);
      toast("success", "Группа удалена");
    },
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      api.post(`/groups/${groupId}/members`, { user_id: userId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["group-members"] });
      setAddMemberId("");
      toast("success", "Участник добавлен");
    },
    onError: (e: any) => toast("error", e?.response?.data?.detail || "Ошибка добавления"),
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      api.delete(`/groups/${groupId}/members/${userId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["group-members"] });
      toast("info", "Участник удалён");
    },
  });

  return (
    <div className="p-6 flex gap-6 h-full">
      {/* Left: Group tree */}
      <div className="flex-1">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">Группы</h1>
        </div>

        <div className="card mb-4">
          <h3 className="font-semibold mb-3">Создать группу</h3>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Название группы"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && newGroupName && createMutation.mutate({ name: newGroupName, parent_id: selectedParent })}
            />
            <button
              className="btn-primary flex items-center gap-2"
              onClick={() => newGroupName && createMutation.mutate({ name: newGroupName, parent_id: selectedParent })}
              disabled={!newGroupName || createMutation.isPending}
            >
              <Plus size={16} />
              Создать
            </button>
          </div>
          {selectedGroup && (
            <p className="text-xs text-gray-500 mt-2">Создать как подгруппу: <b>{selectedGroup.name}</b>
              <button className="ml-2 text-blue-500 underline" onClick={() => { setSelectedGroup(null); setSelectedParent(null); }}>Сбросить</button>
            </p>
          )}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-700" /></div>
        ) : (
          <div className="card p-0 overflow-hidden">
            {groups.length === 0 ? (
              <div className="py-12 text-center text-gray-400">Нет групп. Создайте первую.</div>
            ) : (
              groups.map((g) => (
                <GroupRow
                  key={g.id}
                  group={g}
                  selected={selectedGroup?.id === g.id}
                  onSelect={(group) => { setSelectedGroup(group); setSelectedParent(group.id); }}
                  onDelete={(id) => deleteMutation.mutate(id)}
                />
              ))
            )}
          </div>
        )}
      </div>

      {/* Right: Members panel */}
      {selectedGroup && (
        <div className="w-80 flex-shrink-0">
          <div className="card h-full">
            <div className="flex items-center gap-2 mb-4">
              <Users size={18} className="text-primary-700" />
              <h3 className="font-semibold">{selectedGroup.name}</h3>
            </div>

            <div className="flex gap-2 mb-4">
              <input
                className="input flex-1 text-sm"
                placeholder="ID пользователя"
                value={addMemberId}
                onChange={(e) => setAddMemberId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addMemberId && addMemberMutation.mutate({ groupId: selectedGroup.id, userId: parseInt(addMemberId) })}
              />
              <button
                className="btn-primary px-3"
                onClick={() => addMemberId && addMemberMutation.mutate({ groupId: selectedGroup.id, userId: parseInt(addMemberId) })}
                disabled={!addMemberId}
              >
                <Plus size={14} />
              </button>
            </div>

            <div className="space-y-2">
              {members.map((m) => (
                <div key={m.user_id} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 hover:bg-gray-100">
                  <div>
                    <div className="text-sm font-medium">{m.full_name || `#${m.user_id}`}</div>
                    {m.role && <div className="text-xs text-gray-400">{m.role}</div>}
                  </div>
                  <button
                    className="p-1 text-red-400 hover:text-red-600"
                    onClick={() => removeMemberMutation.mutate({ groupId: selectedGroup.id, userId: m.user_id })}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              {members.length === 0 && <p className="text-xs text-gray-400 text-center py-4">Нет участников</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function GroupRow({ group, selected, onSelect, onDelete, depth = 0 }: {
  group: Group; selected: boolean; onSelect: (g: Group) => void; onDelete: (id: number) => void; depth?: number;
}) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div>
      <div
        className={`flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-100 ${selected ? "bg-green-50" : ""}`}
        style={{ paddingLeft: 16 + depth * 24 }}
        onClick={() => onSelect(group)}
      >
        {group.children.length > 0 ? (
          <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} className="text-gray-400">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : <div className="w-4" />}
        <span className="flex-1 font-medium text-sm">{group.name}</span>
        <span className="text-xs text-gray-400">{group.member_count} чел</span>
        <button
          className="p-1 text-gray-300 hover:text-red-500 ml-1"
          onClick={(e) => { e.stopPropagation(); onDelete(group.id); }}
        >
          <Trash2 size={13} />
        </button>
      </div>
      {expanded && group.children.map((child) => (
        <GroupRow key={child.id} group={child} selected={selected && false} onSelect={onSelect} onDelete={onDelete} depth={depth + 1} />
      ))}
    </div>
  );
}
