'use client';

import React, { useState } from 'react';

interface Segment {
  id: string;
  elements: string[];
}

interface Props {
  data: Segment[];
}

// Human-readable segment descriptions
const segmentDescriptions: Record<string, string> = {
  ISA: 'Interchange Control Header',
  GS: 'Functional Group Header',
  ST: 'Transaction Set Header',
  BHT: 'Beginning of Hierarchical Transaction',
  NM1: 'Individual or Organizational Name',
  N3: 'Address Information',
  N4: 'Geographic Location',
  REF: 'Reference Information',
  PER: 'Administrative Communications Contact',
  HL: 'Hierarchical Level',
  SBR: 'Subscriber Information',
  DMG: 'Demographic Information',
  CLM: 'Claim Information',
  HI: 'Health Care Diagnosis Codes',
  LX: 'Transaction Set Line Number',
  SV1: 'Professional Service',
  DTP: 'Date or Time or Period',
  SE: 'Transaction Set Trailer',
  GE: 'Functional Group Trailer',
  IEA: 'Interchange Control Trailer',
};

// Field names for common segments (by element position)
const elementNames: Record<string, Record<number, string>> = {
  NM1: {
    1: 'Entity Identifier',
    2: 'Entity Type',
    3: 'Last Name',
    4: 'First Name',
    5: 'Middle Name',
    6: 'Name Prefix',
    7: 'Name Suffix',
    8: 'Identification Code Qualifier',
    9: 'Identification Code',
  },
  N3: {
    1: 'Address Line 1',
    2: 'Address Line 2',
  },
  N4: {
    1: 'City',
    2: 'State',
    3: 'Postal Code',
    4: 'Country Code',
  },
  DTP: {
    1: 'Date/Time Qualifier',
    2: 'Date Format Qualifier',
    3: 'Date',
  },
  CLM: {
    1: 'Patient Control Number',
    2: 'Total Claim Charge',
    3: 'Facility Type Code',
    4: 'Claim Frequency Code',
    5: 'Provider Signature Indicator',
  },
  // Add more as needed
};

const ParsedEDIDisplay: React.FC<Props> = ({ data }) => {
  const [expandedSegments, setExpandedSegments] = useState<Set<number>>(new Set());

  const toggleSegment = (index: number) => {
    const newSet = new Set(expandedSegments);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setExpandedSegments(newSet);
  };

  const getElementLabel = (segmentId: string, index: number): string => {
    // Element positions are 1-based in the segment, but array is 0-based
    const pos = index + 1;
    if (elementNames[segmentId] && elementNames[segmentId][pos]) {
      return elementNames[segmentId][pos];
    }
    return `Element ${pos}`;
  };

  return (
    <div className="space-y-2 font-mono text-sm">
      {data.map((seg, idx) => {
        const segId = seg.id;
        const desc = segmentDescriptions[segId] || segId;
        const isExpanded = expandedSegments.has(idx);

        return (
          <div key={idx} className="border rounded bg-white shadow-sm">
            {/* Header */}
            <div
              className={`flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-50 ${
                isExpanded ? 'border-b' : ''
              }`}
              onClick={() => toggleSegment(idx)}
            >
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-blue-700">{segId}</span>
                <span className="text-gray-600">– {desc}</span>
              </div>
              <span className="text-gray-400">
                {isExpanded ? '▼' : '▶'}
              </span>
            </div>

            {/* Elements (shown when expanded) */}
            {isExpanded && (
              <div className="p-3 bg-gray-50 space-y-1">
                {seg.elements.map((elem, elemIdx) => (
                  <div key={elemIdx} className="grid grid-cols-3 gap-2">
                    <span className="text-xs text-gray-500">
                      {getElementLabel(segId, elemIdx)}
                    </span>
                    <span className="col-span-2 font-medium break-all">
                      {elem || <span className="text-gray-400 italic">(empty)</span>}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default ParsedEDIDisplay;